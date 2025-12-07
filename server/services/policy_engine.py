"""Policy Engine - validates actions against defined rules."""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass
class ValidationResult:
    """Result of a policy validation check."""

    allowed: bool
    reason: str | None = None
    matched_rule: str | None = None


class PolicyEngine:
    """
    Evaluates actions against policy rules.

    Policy Schema:
    {
        "version": "1.0",
        "default": "allow" | "block",
        "rules": [
            {
                "action_type": "pay_invoice" | "*",
                "constraints": {
                    "params.amount": {"max": 10000, "min": 0},
                    "params.currency": {"in": ["USD", "EUR"]},
                    "params.vendor": {"not_in": ["BlockedVendor"]},
                    "params.email": {"pattern": ".*@company\\.com$"}
                },
                "allowed_agents": ["invoice_agent", "finance_agent"],
                "blocked_agents": ["untrusted_agent"],
                "rate_limit": {"max_requests": 100, "window_seconds": 3600}
            }
        ]
    }
    """

    def __init__(self):
        self._rate_limit_counters: dict[str, list[datetime]] = {}

    def validate(
        self,
        policy_json: str,
        agent_name: str,
        action_type: str,
        params: dict[str, Any],
    ) -> ValidationResult:
        """Validate an action against a policy."""
        try:
            policy = json.loads(policy_json)
        except json.JSONDecodeError as e:
            return ValidationResult(
                allowed=False, reason=f"Invalid policy JSON: {e}"
            )

        default_action = policy.get("default", "allow")
        rules = policy.get("rules", [])

        # Find matching rules (specific action_type first, then wildcards)
        matching_rules = []
        for rule in rules:
            rule_action = rule.get("action_type", "*")
            if rule_action == action_type or rule_action == "*":
                matching_rules.append(rule)

        # Sort so specific rules come before wildcards
        matching_rules.sort(key=lambda r: 0 if r.get("action_type") != "*" else 1)

        # If no rules match, use default
        if not matching_rules:
            if default_action == "block":
                return ValidationResult(
                    allowed=False,
                    reason=f"Action '{action_type}' not allowed by policy (no matching rules)",
                )
            return ValidationResult(allowed=True)

        # Evaluate each matching rule
        for rule in matching_rules:
            result = self._evaluate_rule(rule, agent_name, action_type, params)
            if not result.allowed:
                return result

        return ValidationResult(allowed=True)

    def _evaluate_rule(
        self,
        rule: dict,
        agent_name: str,
        action_type: str,
        params: dict[str, Any],
    ) -> ValidationResult:
        """Evaluate a single rule against an action."""
        rule_name = rule.get("action_type", "*")

        # Check allowed_agents
        allowed_agents = rule.get("allowed_agents")
        if allowed_agents and agent_name not in allowed_agents:
            return ValidationResult(
                allowed=False,
                reason=f"Agent '{agent_name}' not in allowed agents list",
                matched_rule=rule_name,
            )

        # Check blocked_agents
        blocked_agents = rule.get("blocked_agents", [])
        if agent_name in blocked_agents:
            return ValidationResult(
                allowed=False,
                reason=f"Agent '{agent_name}' is blocked",
                matched_rule=rule_name,
            )

        # Check rate limits
        rate_limit = rule.get("rate_limit")
        if rate_limit:
            result = self._check_rate_limit(
                agent_name, action_type, rate_limit
            )
            if not result.allowed:
                result.matched_rule = rule_name
                return result

        # Check parameter constraints
        constraints = rule.get("constraints", {})
        for param_path, constraint in constraints.items():
            result = self._check_constraint(param_path, constraint, params)
            if not result.allowed:
                result.matched_rule = rule_name
                return result

        return ValidationResult(allowed=True, matched_rule=rule_name)

    def _check_constraint(
        self,
        param_path: str,
        constraint: dict,
        params: dict[str, Any],
    ) -> ValidationResult:
        """Check a single parameter constraint."""
        # Get the value from params using dot notation (e.g., "params.amount" -> params["amount"])
        value = self._get_nested_value(param_path, params)

        # If value is None and we have constraints, that might be an issue
        if value is None:
            # Only fail if there are constraints that require a value
            if any(k in constraint for k in ["min", "max", "in", "not_in", "pattern", "equals"]):
                return ValidationResult(
                    allowed=False,
                    reason=f"Required parameter '{param_path}' is missing",
                )
            return ValidationResult(allowed=True)

        # Check 'max' constraint
        if "max" in constraint:
            try:
                if float(value) > float(constraint["max"]):
                    return ValidationResult(
                        allowed=False,
                        reason=f"Parameter '{param_path}' value {value} exceeds maximum {constraint['max']}",
                    )
            except (ValueError, TypeError):
                return ValidationResult(
                    allowed=False,
                    reason=f"Parameter '{param_path}' cannot be compared numerically",
                )

        # Check 'min' constraint
        if "min" in constraint:
            try:
                if float(value) < float(constraint["min"]):
                    return ValidationResult(
                        allowed=False,
                        reason=f"Parameter '{param_path}' value {value} is below minimum {constraint['min']}",
                    )
            except (ValueError, TypeError):
                return ValidationResult(
                    allowed=False,
                    reason=f"Parameter '{param_path}' cannot be compared numerically",
                )

        # Check 'in' constraint (whitelist)
        if "in" in constraint:
            allowed_values = constraint["in"]
            if value not in allowed_values:
                return ValidationResult(
                    allowed=False,
                    reason=f"Parameter '{param_path}' value '{value}' not in allowed values {allowed_values}",
                )

        # Check 'not_in' constraint (blacklist)
        if "not_in" in constraint:
            blocked_values = constraint["not_in"]
            if value in blocked_values:
                return ValidationResult(
                    allowed=False,
                    reason=f"Parameter '{param_path}' value '{value}' is blocked",
                )

        # Check 'pattern' constraint (regex)
        if "pattern" in constraint:
            pattern = constraint["pattern"]
            if not re.match(pattern, str(value)):
                return ValidationResult(
                    allowed=False,
                    reason=f"Parameter '{param_path}' value '{value}' does not match pattern '{pattern}'",
                )

        # Check 'equals' constraint
        if "equals" in constraint:
            if value != constraint["equals"]:
                return ValidationResult(
                    allowed=False,
                    reason=f"Parameter '{param_path}' must equal '{constraint['equals']}'",
                )

        return ValidationResult(allowed=True)

    def _get_nested_value(self, path: str, params: dict[str, Any]) -> Any:
        """Get a value from params using dot notation path."""
        # Remove 'params.' prefix if present
        if path.startswith("params."):
            path = path[7:]

        parts = path.split(".")
        value = params
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value

    def _check_rate_limit(
        self,
        agent_name: str,
        action_type: str,
        rate_limit: dict,
    ) -> ValidationResult:
        """Check rate limiting for an action."""
        max_requests = rate_limit.get("max_requests", 100)
        window_seconds = rate_limit.get("window_seconds", 3600)

        key = f"{agent_name}:{action_type}"
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=window_seconds)

        # Get or create counter for this key
        if key not in self._rate_limit_counters:
            self._rate_limit_counters[key] = []

        # Clean old entries
        self._rate_limit_counters[key] = [
            ts for ts in self._rate_limit_counters[key] if ts > window_start
        ]

        # Check if over limit
        if len(self._rate_limit_counters[key]) >= max_requests:
            return ValidationResult(
                allowed=False,
                reason=f"Rate limit exceeded: {max_requests} requests per {window_seconds}s",
            )

        # Record this request
        self._rate_limit_counters[key].append(now)
        return ValidationResult(allowed=True)

    def clear_rate_limits(self) -> None:
        """Clear all rate limit counters (useful for testing)."""
        self._rate_limit_counters.clear()


# Singleton instance
_engine: PolicyEngine | None = None


def get_policy_engine() -> PolicyEngine:
    """Get the singleton policy engine instance."""
    global _engine
    if _engine is None:
        _engine = PolicyEngine()
    return _engine
