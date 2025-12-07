"""Validator service - orchestrates policy validation and logging."""

import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.models import Policy, AuditLog
from server.services.policy_engine import get_policy_engine, ValidationResult


@dataclass
class ActionValidationResult:
    """Complete result of an action validation."""

    allowed: bool
    action_id: str
    reason: str | None = None
    timestamp: datetime = None
    execution_time_ms: int = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        result = {
            "allowed": self.allowed,
            "action_id": self.action_id,
            "timestamp": self.timestamp.isoformat() + "Z",
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

    async def validate_action(
        self,
        project_id: str,
        agent_name: str,
        action_type: str,
        params: dict[str, Any],
    ) -> ActionValidationResult:
        """
        Validate an action against the project's active policy.

        Returns the validation result and logs the attempt.
        """
        start_time = time.perf_counter()

        # Get active policy for project
        policy = await self._get_active_policy(project_id)

        if policy is None:
            # No policy = allow by default (but still log)
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

        execution_time_ms = int((time.perf_counter() - start_time) * 1000)

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

        return ActionValidationResult(
            allowed=result.allowed,
            action_id=audit_log.action_id,
            reason=result.reason,
            timestamp=audit_log.timestamp,
            execution_time_ms=execution_time_ms,
        )

    async def _get_active_policy(self, project_id: str) -> Policy | None:
        """Get the active policy for a project."""
        stmt = (
            select(Policy)
            .where(Policy.project_id == project_id)
            .where(Policy.is_active == True)
            .order_by(Policy.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


async def get_validator(db: AsyncSession) -> ValidatorService:
    """Factory function to create a validator service."""
    return ValidatorService(db)
