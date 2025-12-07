"""
Unit tests for the Policy Engine.

Tests cover:
1. Constraint validation (max, min, in, not_in, pattern, not_pattern, equals)
2. Rate limiting logic
3. Agent authorization
4. Policy matching logic
"""

import json
import time
import pytest
from unittest.mock import patch
from datetime import datetime, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from server.services.policy_engine import PolicyEngine, ValidationResult


def make_policy(rules: list, default: str = "block") -> str:
    """Helper to create policy JSON."""
    return json.dumps({
        "name": "test-policy",
        "version": "1.0",
        "default": default,
        "rules": rules
    })


# =============================================================================
# CONSTRAINT VALIDATION TESTS - Max/Min
# =============================================================================

class TestMaxConstraint:
    """Tests for the 'max' constraint."""

    def test_allows_value_under_limit(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "pay",
            "constraints": {"params.amount": {"max": 500}}
        }])

        result = engine.validate(policy, "agent", "pay", {"amount": 450})
        assert result.allowed is True

    def test_blocks_value_over_limit(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "pay",
            "constraints": {"params.amount": {"max": 500}}
        }])

        result = engine.validate(policy, "agent", "pay", {"amount": 600})
        assert result.allowed is False
        assert "exceeds maximum" in result.reason

    def test_allows_value_exactly_at_limit(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "pay",
            "constraints": {"params.amount": {"max": 500}}
        }])

        result = engine.validate(policy, "agent", "pay", {"amount": 500})
        assert result.allowed is True

    def test_handles_float_values(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "pay",
            "constraints": {"params.amount": {"max": 100.50}}
        }])

        result = engine.validate(policy, "agent", "pay", {"amount": 100.49})
        assert result.allowed is True

        result = engine.validate(policy, "agent", "pay", {"amount": 100.51})
        assert result.allowed is False


class TestMinConstraint:
    """Tests for the 'min' constraint."""

    def test_allows_value_above_minimum(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "pay",
            "constraints": {"params.amount": {"min": 1}}
        }])

        result = engine.validate(policy, "agent", "pay", {"amount": 50})
        assert result.allowed is True

    def test_blocks_value_below_minimum(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "pay",
            "constraints": {"params.amount": {"min": 1}}
        }])

        result = engine.validate(policy, "agent", "pay", {"amount": 0.5})
        assert result.allowed is False
        assert "below minimum" in result.reason

    def test_allows_value_exactly_at_minimum(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "pay",
            "constraints": {"params.amount": {"min": 1}}
        }])

        result = engine.validate(policy, "agent", "pay", {"amount": 1})
        assert result.allowed is True

    def test_combined_min_max(self):
        """Test both min and max constraints together."""
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "pay",
            "constraints": {"params.amount": {"min": 10, "max": 100}}
        }])

        # Below min
        result = engine.validate(policy, "agent", "pay", {"amount": 5})
        assert result.allowed is False

        # Above max
        result = engine.validate(policy, "agent", "pay", {"amount": 150})
        assert result.allowed is False

        # Within range
        result = engine.validate(policy, "agent", "pay", {"amount": 50})
        assert result.allowed is True


# =============================================================================
# CONSTRAINT VALIDATION TESTS - In/Not_In
# =============================================================================

class TestInConstraint:
    """Tests for the 'in' (whitelist) constraint."""

    def test_allows_whitelisted_value(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "pay",
            "constraints": {"params.vendor": {"in": ["VendorA", "VendorB", "VendorC"]}}
        }])

        result = engine.validate(policy, "agent", "pay", {"vendor": "VendorA"})
        assert result.allowed is True

    def test_blocks_non_whitelisted_value(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "pay",
            "constraints": {"params.vendor": {"in": ["VendorA", "VendorB"]}}
        }])

        result = engine.validate(policy, "agent", "pay", {"vendor": "UnknownVendor"})
        assert result.allowed is False
        assert "not in allowed values" in result.reason

    def test_case_sensitive(self):
        """'in' constraint should be case-sensitive."""
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "pay",
            "constraints": {"params.vendor": {"in": ["VendorA"]}}
        }])

        result = engine.validate(policy, "agent", "pay", {"vendor": "vendora"})
        assert result.allowed is False


class TestNotInConstraint:
    """Tests for the 'not_in' (blacklist) constraint."""

    def test_blocks_blacklisted_value(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "pay",
            "constraints": {"params.vendor": {"not_in": ["BlockedVendor", "BadActor"]}}
        }])

        result = engine.validate(policy, "agent", "pay", {"vendor": "BlockedVendor"})
        assert result.allowed is False
        assert "is blocked" in result.reason

    def test_allows_non_blacklisted_value(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "pay",
            "constraints": {"params.vendor": {"not_in": ["BlockedVendor"]}}
        }])

        result = engine.validate(policy, "agent", "pay", {"vendor": "GoodVendor"})
        assert result.allowed is True


# =============================================================================
# CONSTRAINT VALIDATION TESTS - Pattern
# =============================================================================

class TestPatternConstraint:
    """Tests for the 'pattern' (regex match required) constraint."""

    def test_allows_matching_pattern(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "send_email",
            "constraints": {"params.email": {"pattern": r".*@company\.com$"}}
        }])

        result = engine.validate(policy, "agent", "send_email", {"email": "user@company.com"})
        assert result.allowed is True

    def test_blocks_non_matching_pattern(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "send_email",
            "constraints": {"params.email": {"pattern": r".*@company\.com$"}}
        }])

        result = engine.validate(policy, "agent", "send_email", {"email": "user@external.com"})
        assert result.allowed is False
        assert "does not match pattern" in result.reason


class TestNotPatternConstraint:
    """Tests for the 'not_pattern' (regex must NOT match) constraint - for PII detection."""

    def test_blocks_ssn_pattern(self):
        engine = PolicyEngine()
        ssn_pattern = r'\b\d{3}-\d{2}-\d{4}\b'
        policy = make_policy([{
            "action_type": "send_response",
            "constraints": {
                "params.response_text": {
                    "not_pattern": ssn_pattern,
                    "reason": "SSN detected"
                }
            }
        }])

        result = engine.validate(
            policy, "agent", "send_response",
            {"response_text": "Your SSN is 123-45-6789"}
        )
        assert result.allowed is False
        assert "SSN detected" in result.reason

    def test_allows_text_without_ssn(self):
        engine = PolicyEngine()
        ssn_pattern = r'\b\d{3}-\d{2}-\d{4}\b'
        policy = make_policy([{
            "action_type": "send_response",
            "constraints": {
                "params.response_text": {
                    "not_pattern": ssn_pattern,
                    "reason": "SSN detected"
                }
            }
        }])

        result = engine.validate(
            policy, "agent", "send_response",
            {"response_text": "Thank you for contacting support."}
        )
        assert result.allowed is True

    def test_blocks_credit_card_pattern(self):
        engine = PolicyEngine()
        cc_pattern = r'\b(?:\d{4}[-\s]?){3}\d{4}\b'
        policy = make_policy([{
            "action_type": "send_response",
            "constraints": {
                "params.response_text": {
                    "not_pattern": cc_pattern,
                    "reason": "Credit card number detected"
                }
            }
        }])

        result = engine.validate(
            policy, "agent", "send_response",
            {"response_text": "Your card 4111-1111-1111-1111 has been charged"}
        )
        assert result.allowed is False


# =============================================================================
# CONSTRAINT VALIDATION TESTS - Equals
# =============================================================================

class TestEqualsConstraint:
    """Tests for the 'equals' constraint."""

    def test_allows_exact_match(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "close_ticket",
            "constraints": {"params.has_reviewed_tag": {"equals": True}}
        }])

        result = engine.validate(policy, "agent", "close_ticket", {"has_reviewed_tag": True})
        assert result.allowed is True

    def test_blocks_mismatch(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "close_ticket",
            "constraints": {"params.has_reviewed_tag": {"equals": True}}
        }])

        result = engine.validate(policy, "agent", "close_ticket", {"has_reviewed_tag": False})
        assert result.allowed is False
        assert "must equal" in result.reason

    def test_string_equality(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "update",
            "constraints": {"params.status": {"equals": "approved"}}
        }])

        result = engine.validate(policy, "agent", "update", {"status": "approved"})
        assert result.allowed is True

        result = engine.validate(policy, "agent", "update", {"status": "pending"})
        assert result.allowed is False


# =============================================================================
# CONSTRAINT VALIDATION TESTS - Contains/Not Contains
# =============================================================================

class TestContainsConstraint:
    """Tests for the 'contains' constraint."""

    def test_allows_when_substring_present(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "log",
            "constraints": {"params.message": {"contains": "[AUDIT]"}}
        }])

        result = engine.validate(policy, "agent", "log", {"message": "[AUDIT] User logged in"})
        assert result.allowed is True

    def test_blocks_when_substring_missing(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "log",
            "constraints": {"params.message": {"contains": "[AUDIT]"}}
        }])

        result = engine.validate(policy, "agent", "log", {"message": "User logged in"})
        assert result.allowed is False


class TestNotContainsConstraint:
    """Tests for the 'not_contains' constraint."""

    def test_blocks_when_substring_present(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "send",
            "constraints": {"params.text": {"not_contains": "password"}}
        }])

        result = engine.validate(policy, "agent", "send", {"text": "Your password is 123"})
        assert result.allowed is False

    def test_allows_when_substring_missing(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "send",
            "constraints": {"params.text": {"not_contains": "password"}}
        }])

        result = engine.validate(policy, "agent", "send", {"text": "Hello, how can I help?"})
        assert result.allowed is True


# =============================================================================
# RATE LIMITING TESTS
# =============================================================================

class TestRateLimiting:
    """Tests for rate limiting logic."""

    def test_allows_under_limit(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "api_call",
            "rate_limit": {"max_requests": 5, "window_seconds": 60}
        }])

        # First 5 requests should pass
        for i in range(5):
            result = engine.validate(policy, "agent", "api_call", {})
            assert result.allowed is True, f"Request {i+1} should be allowed"

    def test_blocks_when_limit_exceeded(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "api_call",
            "rate_limit": {"max_requests": 3, "window_seconds": 60}
        }])

        # First 3 requests pass
        for _ in range(3):
            engine.validate(policy, "agent", "api_call", {})

        # 4th request should be blocked
        result = engine.validate(policy, "agent", "api_call", {})
        assert result.allowed is False
        assert "Rate limit exceeded" in result.reason

    def test_rate_limit_per_agent_action_pair(self):
        """Different agent/action combinations have separate limits."""
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "*",
            "rate_limit": {"max_requests": 2, "window_seconds": 60}
        }])

        # Agent1 + action1: 2 requests
        engine.validate(policy, "agent1", "action1", {})
        engine.validate(policy, "agent1", "action1", {})
        result = engine.validate(policy, "agent1", "action1", {})
        assert result.allowed is False  # Blocked

        # Agent1 + action2: fresh limit
        result = engine.validate(policy, "agent1", "action2", {})
        assert result.allowed is True

        # Agent2 + action1: fresh limit
        result = engine.validate(policy, "agent2", "action1", {})
        assert result.allowed is True

    def test_rate_limit_resets_after_window(self):
        """Rate limit should reset after the window expires."""
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "api_call",
            "rate_limit": {"max_requests": 2, "window_seconds": 1}
        }])

        # Use up the limit
        engine.validate(policy, "agent", "api_call", {})
        engine.validate(policy, "agent", "api_call", {})
        result = engine.validate(policy, "agent", "api_call", {})
        assert result.allowed is False

        # Wait for window to expire
        time.sleep(1.1)

        # Should be allowed again
        result = engine.validate(policy, "agent", "api_call", {})
        assert result.allowed is True

    def test_clear_rate_limits(self):
        """Test that rate limits can be cleared."""
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "api_call",
            "rate_limit": {"max_requests": 1, "window_seconds": 3600}
        }])

        engine.validate(policy, "agent", "api_call", {})
        result = engine.validate(policy, "agent", "api_call", {})
        assert result.allowed is False

        engine.clear_rate_limits()

        result = engine.validate(policy, "agent", "api_call", {})
        assert result.allowed is True


# =============================================================================
# AGENT AUTHORIZATION TESTS
# =============================================================================

class TestAgentAuthorization:
    """Tests for agent authorization (allowed_agents, blocked_agents)."""

    def test_allowed_agents_permits_listed_agent(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "pay",
            "allowed_agents": ["finance_agent", "admin_agent"]
        }])

        result = engine.validate(policy, "finance_agent", "pay", {})
        assert result.allowed is True

    def test_allowed_agents_blocks_unlisted_agent(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "pay",
            "allowed_agents": ["finance_agent", "admin_agent"]
        }])

        result = engine.validate(policy, "random_agent", "pay", {})
        assert result.allowed is False
        assert "not in allowed agents" in result.reason

    def test_blocked_agents_blocks_listed_agent(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "pay",
            "blocked_agents": ["untrusted_agent", "test_agent"]
        }])

        result = engine.validate(policy, "untrusted_agent", "pay", {})
        assert result.allowed is False
        assert "is blocked" in result.reason

    def test_blocked_agents_allows_unlisted_agent(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "pay",
            "blocked_agents": ["untrusted_agent"]
        }])

        result = engine.validate(policy, "trusted_agent", "pay", {})
        assert result.allowed is True

    def test_no_agent_restriction_allows_any_agent(self):
        """When neither allowed_agents nor blocked_agents is specified."""
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "read",
            "constraints": {}
        }])

        result = engine.validate(policy, "any_agent", "read", {})
        assert result.allowed is True


# =============================================================================
# POLICY MATCHING TESTS
# =============================================================================

class TestPolicyMatching:
    """Tests for policy rule matching logic."""

    def test_specific_rule_matches_before_wildcard(self):
        engine = PolicyEngine()
        policy = make_policy([
            {"action_type": "*", "constraints": {"params.amount": {"max": 1000}}},
            {"action_type": "pay", "constraints": {"params.amount": {"max": 100}}}
        ])

        # Specific "pay" rule should apply (max 100), not wildcard (max 1000)
        result = engine.validate(policy, "agent", "pay", {"amount": 150})
        assert result.allowed is False

        # Other actions use wildcard rule
        result = engine.validate(policy, "agent", "transfer", {"amount": 500})
        assert result.allowed is True

    def test_wildcard_rule_matches_any_action(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "*",
            "constraints": {"params.amount": {"max": 100}}
        }])

        result = engine.validate(policy, "agent", "any_action", {"amount": 50})
        assert result.allowed is True

        result = engine.validate(policy, "agent", "another_action", {"amount": 150})
        assert result.allowed is False

    def test_default_block_when_no_rules_match(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "allowed_action",
            "constraints": {}
        }], default="block")

        result = engine.validate(policy, "agent", "unknown_action", {})
        assert result.allowed is False
        assert "no matching rules" in result.reason

    def test_default_allow_when_no_rules_match(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "specific_action",
            "constraints": {}
        }], default="allow")

        result = engine.validate(policy, "agent", "any_other_action", {})
        assert result.allowed is True

    def test_multiple_constraints_all_must_pass(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "pay",
            "constraints": {
                "params.amount": {"max": 500, "min": 1},
                "params.vendor": {"in": ["VendorA", "VendorB"]}
            }
        }])

        # All constraints pass
        result = engine.validate(policy, "agent", "pay", {"amount": 100, "vendor": "VendorA"})
        assert result.allowed is True

        # Amount fails
        result = engine.validate(policy, "agent", "pay", {"amount": 600, "vendor": "VendorA"})
        assert result.allowed is False

        # Vendor fails
        result = engine.validate(policy, "agent", "pay", {"amount": 100, "vendor": "UnknownVendor"})
        assert result.allowed is False

    def test_nested_param_path_resolution(self):
        """Test that dot notation paths work for nested params."""
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "create_user",
            "constraints": {"params.user.role": {"in": ["user", "admin"]}}
        }])

        result = engine.validate(policy, "agent", "create_user", {"user": {"role": "admin"}})
        assert result.allowed is True

        result = engine.validate(policy, "agent", "create_user", {"user": {"role": "superuser"}})
        assert result.allowed is False

    def test_missing_required_parameter(self):
        """When a required parameter is missing."""
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "pay",
            "constraints": {"params.amount": {"max": 500}}
        }])

        # Missing 'amount' parameter
        result = engine.validate(policy, "agent", "pay", {"vendor": "VendorA"})
        assert result.allowed is False
        assert "missing" in result.reason.lower()


# =============================================================================
# EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_invalid_policy_json(self):
        engine = PolicyEngine()
        result = engine.validate("not valid json", "agent", "action", {})
        assert result.allowed is False
        assert "Invalid policy JSON" in result.reason

    def test_empty_rules_list_uses_default(self):
        engine = PolicyEngine()
        policy = make_policy([], default="allow")
        result = engine.validate(policy, "agent", "action", {})
        assert result.allowed is True

        policy = make_policy([], default="block")
        result = engine.validate(policy, "agent", "action", {})
        assert result.allowed is False

    def test_non_numeric_value_for_numeric_constraint(self):
        engine = PolicyEngine()
        policy = make_policy([{
            "action_type": "pay",
            "constraints": {"params.amount": {"max": 500}}
        }])

        result = engine.validate(policy, "agent", "pay", {"amount": "not a number"})
        assert result.allowed is False
        assert "cannot be compared numerically" in result.reason

    def test_multiple_rules_for_same_action(self):
        """When multiple rules match the same action, all are evaluated."""
        engine = PolicyEngine()
        policy = make_policy([
            {"action_type": "pay", "constraints": {"params.amount": {"max": 500}}},
            {"action_type": "pay", "allowed_agents": ["finance_agent"]}
        ])

        # Must pass both rules
        result = engine.validate(policy, "finance_agent", "pay", {"amount": 100})
        assert result.allowed is True

        # Fails amount constraint
        result = engine.validate(policy, "finance_agent", "pay", {"amount": 600})
        assert result.allowed is False

        # Fails agent constraint
        result = engine.validate(policy, "other_agent", "pay", {"amount": 100})
        assert result.allowed is False
