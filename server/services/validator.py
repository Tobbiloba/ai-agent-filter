"""Validator service - orchestrates policy validation and logging."""

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.models import Policy, AuditLog
from server.services.policy_engine import get_policy_engine, ValidationResult
from server.services.aggregate import AggregateService
from server.cache import get_cache

logger = logging.getLogger(__name__)


@dataclass
class ActionValidationResult:
    """Complete result of an action validation."""

    allowed: bool
    action_id: str | None
    reason: str | None = None
    timestamp: datetime = None
    execution_time_ms: int = None
    simulated: bool = False

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        result = {
            "allowed": self.allowed,
            "action_id": self.action_id,
            "timestamp": self.timestamp.isoformat() + "Z",
            "simulated": self.simulated,
        }
        if not self.allowed and self.reason:
            result["reason"] = self.reason
        if self.execution_time_ms is not None:
            result["execution_time_ms"] = self.execution_time_ms
        return result


class ValidatorService:
    """Service for validating actions and logging results."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.engine = get_policy_engine()
        self.aggregate_service = AggregateService(db)

    async def validate_action(
        self,
        project_id: str,
        agent_name: str,
        action_type: str,
        params: dict[str, Any],
        simulate: bool = False,
    ) -> ActionValidationResult:
        """
        Validate an action against the project's active policy.

        Validation order:
        1. Basic policy rules (constraints, rate limits, agent lists)
        2. Aggregate limits (cumulative limits across time windows)

        Args:
            project_id: The project identifier
            agent_name: Name of the agent performing the action
            action_type: Type of action being performed
            params: Action parameters
            simulate: If True, run validation without logging or affecting state
                     (what-if mode for testing policies)

        Returns the validation result and logs the attempt (unless simulating).
        """
        start_time = time.perf_counter()

        # Get active policy for project
        policy = await self._get_active_policy(project_id)

        if policy is None:
            # No policy = allow by default (but still log unless simulating)
            result = ValidationResult(allowed=True, reason="No policy configured")
            policy_version = None
            policy_rules = json.dumps({"default": "allow", "rules": []})
        else:
            policy_version = policy.version
            policy_rules = policy.rules
            result = self.engine.validate(
                policy_json=policy_rules,
                agent_name=agent_name,
                action_type=action_type,
                params=params,
            )

            # If basic validation passed, check aggregate limits
            if result.allowed:
                aggregate_result = await self._check_aggregate_limits(
                    policy_rules, project_id, agent_name, action_type, params
                )
                if not aggregate_result.allowed:
                    result = aggregate_result

        execution_time_ms = int((time.perf_counter() - start_time) * 1000)

        # In simulation mode, skip audit logging and cache invalidation
        if simulate:
            return ActionValidationResult(
                allowed=result.allowed,
                action_id=None,  # No action_id for simulations
                reason=result.reason,
                timestamp=datetime.utcnow(),
                execution_time_ms=execution_time_ms,
                simulated=True,
            )

        # Create audit log entry
        audit_log = AuditLog(
            project_id=project_id,
            agent_name=agent_name,
            action_type=action_type,
            params=json.dumps(params),
            allowed=result.allowed,
            reason=result.reason,
            policy_version=policy_version,
            execution_time_ms=execution_time_ms,
        )
        self.db.add(audit_log)
        await self.db.flush()  # Get the generated action_id

        # Invalidate aggregate cache if action was allowed
        # (next check will recalculate from DB including this action)
        if result.allowed:
            await self.aggregate_service.invalidate_cache(
                project_id, agent_name, action_type
            )

        return ActionValidationResult(
            allowed=result.allowed,
            action_id=audit_log.action_id,
            reason=result.reason,
            timestamp=audit_log.timestamp,
            execution_time_ms=execution_time_ms,
            simulated=False,
        )

    async def _check_aggregate_limits(
        self,
        policy_rules: str,
        project_id: str,
        agent_name: str,
        action_type: str,
        params: dict[str, Any],
    ) -> ValidationResult:
        """Check aggregate limits for matching rules.

        Returns ValidationResult with allowed=False if any limit exceeded.
        """
        try:
            policy = json.loads(policy_rules)
        except json.JSONDecodeError:
            return ValidationResult(allowed=True)  # Invalid JSON, skip aggregate check

        rules = policy.get("rules", [])

        for rule in rules:
            rule_action = rule.get("action_type", "*")
            # Check if rule matches this action
            if rule_action != action_type and rule_action != "*":
                continue

            aggregate_limit = rule.get("aggregate_limit")
            if not aggregate_limit:
                continue

            # Check this aggregate limit
            result = await self._check_single_aggregate_limit(
                aggregate_limit, project_id, agent_name, action_type, params
            )
            if not result.allowed:
                return result

        return ValidationResult(allowed=True)

    async def _check_single_aggregate_limit(
        self,
        config: dict[str, Any],
        project_id: str,
        agent_name: str,
        action_type: str,
        params: dict[str, Any],
    ) -> ValidationResult:
        """Check a single aggregate limit configuration."""
        max_value = config.get("max_value")
        if max_value is None:
            return ValidationResult(allowed=True)  # No limit set

        param_path = config.get("param_path", "amount")
        measure = config.get("measure", "sum")
        window = config.get("window", "daily")

        # Get current aggregate total
        current_total = await self.aggregate_service.get_current_total(
            project_id, agent_name, action_type, config
        )

        # Calculate projected total
        if measure == "count":
            # Count measure: just add 1 for this action
            projected_total = current_total + 1
        else:
            # Sum measure: extract value from params
            new_value = self._extract_param_value(params, param_path)
            if new_value is None:
                new_value = 0
            projected_total = current_total + new_value

        # Check if would exceed limit
        if projected_total > max_value:
            scope = config.get("scope", "agent")
            return ValidationResult(
                allowed=False,
                reason=(
                    f"Aggregate limit exceeded: {projected_total:.2f} > {max_value:.2f} "
                    f"({window} window, {scope} scope)"
                ),
            )

        return ValidationResult(allowed=True)

    def _extract_param_value(self, params: dict[str, Any], path: str) -> float | None:
        """Extract numeric value from params using dot notation path."""
        try:
            parts = path.split(".")
            value = params
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    return None
            if value is None:
                return None
            return float(value)
        except (ValueError, TypeError):
            return None

    async def _get_active_policy(self, project_id: str) -> Policy | None:
        """Get the active policy for a project (with caching)."""
        cache = get_cache()

        # Try cache first
        cached = await cache.get_policy(project_id)
        if cached:
            return self._policy_from_cache(cached)

        # Cache miss - fetch from database
        stmt = (
            select(Policy)
            .where(Policy.project_id == project_id)
            .where(Policy.is_active == True)
            .order_by(Policy.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        policy = result.scalar_one_or_none()

        # Cache the result
        if policy:
            await cache.set_policy(project_id, {
                "id": policy.id,
                "project_id": policy.project_id,
                "name": policy.name,
                "version": policy.version,
                "rules": policy.rules,
                "is_active": policy.is_active,
            })

        return policy

    def _policy_from_cache(self, data: dict) -> Policy:
        """Reconstruct Policy object from cached data."""
        policy = Policy(
            id=data["id"],
            project_id=data["project_id"],
            name=data["name"],
            version=data["version"],
            rules=data["rules"],
            is_active=data["is_active"],
        )
        return policy


async def get_validator(db: AsyncSession) -> ValidatorService:
    """Factory function to create a validator service."""
    return ValidatorService(db)
