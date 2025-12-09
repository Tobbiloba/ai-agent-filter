"""E2E tests for edge cases and boundary conditions.

Tests empty policies, rate limits, wildcards, concurrent requests, and constraint edge cases.
"""

import time
from concurrent.futures import ThreadPoolExecutor

import pytest


class TestEdgeCases:
    """E2E tests for boundary conditions and edge cases."""

    def test_empty_policy_default_allow(
        self, create_project, create_policy, validate_action
    ):
        """Policy with no rules and default: 'allow'."""
        project_id, api_key = create_project("-empty-allow")

        # Empty rules, default allow
        create_policy(project_id, api_key, [], default="allow")

        # Any action should be allowed
        status, result = validate_action(
            project_id, api_key, "any_agent", "any_action", {"any": "params"}
        )
        assert result["allowed"] is True

    def test_empty_policy_default_block(
        self, create_project, create_policy, validate_action
    ):
        """Policy with no rules and default: 'block'."""
        project_id, api_key = create_project("-empty-block")

        # Empty rules, default block
        create_policy(project_id, api_key, [], default="block")

        # Any action should be blocked
        status, result = validate_action(
            project_id, api_key, "any_agent", "any_action", {"any": "params"}
        )
        assert result["allowed"] is False
        assert "no matching rules" in result["reason"].lower()

    def test_validation_without_policy_allows_by_default(
        self, client, create_project
    ):
        """Project without policy allows actions by default."""
        project_id, api_key = create_project("-no-policy")

        # Don't create a policy, try to validate
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "agent",
                "action_type": "action",
                "params": {}
            },
            headers={"X-API-Key": api_key}
        )

        # No policy = allow by default
        assert response.status_code == 200
        result = response.json()
        assert result["allowed"] is True

    def test_deactivated_project_cannot_validate(
        self, client, create_project, create_policy
    ):
        """Deactivated project returns 403."""
        project_id, api_key = create_project("-deactivated")
        create_policy(project_id, api_key, [
            {"action_type": "*", "allowed_agents": ["agent"]}
        ])

        # Deactivate the project
        response = client.delete(f"/projects/{project_id}")
        assert response.status_code == 200

        # Try to validate
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "agent",
                "action_type": "action",
                "params": {}
            },
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 403

    def test_rate_limit_reset_after_window(
        self, create_project, create_policy, validate_action
    ):
        """Rate limit resets after window_seconds (simulated with short window)."""
        project_id, api_key = create_project("-rate-reset")

        # Very short window (1 second) for testing
        create_policy(project_id, api_key, [
            {
                "action_type": "quick_action",
                "allowed_agents": ["agent"],
                "rate_limit": {"max_requests": 2, "window_seconds": 1}
            }
        ])

        # Use up the limit
        validate_action(project_id, api_key, "agent", "quick_action", {"i": 1})
        validate_action(project_id, api_key, "agent", "quick_action", {"i": 2})

        status, result = validate_action(
            project_id, api_key, "agent", "quick_action", {"i": 3}
        )
        assert result["allowed"] is False

        # Wait for window to expire
        time.sleep(1.1)

        # Should be allowed again
        status, result = validate_action(
            project_id, api_key, "agent", "quick_action", {"i": 4}
        )
        assert result["allowed"] is True

    def test_rate_limit_per_action_type(
        self, create_project, create_policy, validate_action
    ):
        """Rate limits are tracked per action_type, not globally for wildcards."""
        project_id, api_key = create_project("-rate-per-action")

        # Rate limit per action type
        create_policy(project_id, api_key, [
            {
                "action_type": "*",
                "allowed_agents": ["agent"],
                "rate_limit": {"max_requests": 2, "window_seconds": 60}
            }
        ], default="allow")

        # Each action type has its own limit counter
        # action_a: 2 requests
        validate_action(project_id, api_key, "agent", "action_a", {})
        validate_action(project_id, api_key, "agent", "action_a", {})

        # 3rd action_a should be blocked
        status, result = validate_action(
            project_id, api_key, "agent", "action_a", {}
        )
        assert result["allowed"] is False
        assert "Rate limit exceeded" in result["reason"]

        # But action_b still has its own limit
        status, result = validate_action(
            project_id, api_key, "agent", "action_b", {}
        )
        assert result["allowed"] is True

    def test_concurrent_validations_same_project(
        self, client, create_project, create_policy
    ):
        """High concurrency doesn't corrupt state."""
        project_id, api_key = create_project("-concurrent")

        create_policy(project_id, api_key, [
            {
                "action_type": "concurrent",
                "constraints": {"params.value": {"max": 100}},
                "allowed_agents": ["agent"]
            }
        ])

        def validate(index):
            # Use values that are clearly allowed (0-49) or blocked (101-150)
            value = index if index < 25 else 101 + (index - 25)
            response = client.post(
                "/validate_action",
                json={
                    "project_id": project_id,
                    "agent_name": "agent",
                    "action_type": "concurrent",
                    "params": {"value": value}
                },
                headers={"X-API-Key": api_key}
            )
            return response.status_code, response.json(), value

        # Run 50 concurrent validations
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(validate, i) for i in range(50)]
            results = [f.result() for f in futures]

        # All should complete successfully (status 200)
        assert all(status == 200 for status, _, _ in results)

        # Verify correctness of each result
        for status, result, value in results:
            if value <= 100:
                assert result["allowed"] is True, f"Value {value} should be allowed"
            else:
                assert result["allowed"] is False, f"Value {value} should be blocked"

        # Count allowed vs blocked
        allowed = sum(1 for _, r, _ in results if r["allowed"])
        blocked = sum(1 for _, r, _ in results if not r["allowed"])

        # Should have both (25 allowed, 25 blocked)
        assert allowed == 25
        assert blocked == 25

    def test_wildcard_action_type(
        self, create_project, create_policy, validate_action
    ):
        """action_type: '*' matches all action types."""
        project_id, api_key = create_project("-wildcard")

        create_policy(project_id, api_key, [
            {
                "action_type": "*",
                "constraints": {"params.valid": {"equals": True}},
                "allowed_agents": ["agent"]
            }
        ])

        # Various action types all match wildcard
        for action in ["send_email", "delete_file", "make_payment", "random_action"]:
            status, result = validate_action(
                project_id, api_key, "agent", action, {"valid": True}
            )
            assert result["allowed"] is True, f"Action {action} should be allowed"

            status, result = validate_action(
                project_id, api_key, "agent", action, {"valid": False}
            )
            assert result["allowed"] is False, f"Action {action} should be blocked"

    def test_nested_params_constraint(
        self, create_project, create_policy, validate_action
    ):
        """Deep param path like params.invoice.amount."""
        project_id, api_key = create_project("-nested")

        create_policy(project_id, api_key, [
            {
                "action_type": "process_invoice",
                "constraints": {
                    "params.invoice.amount": {"max": 1000},
                    "params.invoice.currency": {"in": ["USD", "EUR"]}
                },
                "allowed_agents": ["agent"]
            }
        ])

        # Valid nested params
        status, result = validate_action(
            project_id, api_key, "agent", "process_invoice",
            {"invoice": {"amount": 500, "currency": "USD"}}
        )
        assert result["allowed"] is True

        # Invalid nested amount
        status, result = validate_action(
            project_id, api_key, "agent", "process_invoice",
            {"invoice": {"amount": 2000, "currency": "USD"}}
        )
        assert result["allowed"] is False
        assert "exceeds maximum" in result["reason"]

        # Invalid nested currency
        status, result = validate_action(
            project_id, api_key, "agent", "process_invoice",
            {"invoice": {"amount": 500, "currency": "GBP"}}
        )
        assert result["allowed"] is False
        assert "not in allowed values" in result["reason"]

    def test_pattern_constraint_regex(
        self, create_project, create_policy, validate_action
    ):
        """Pattern constraint with regex validation."""
        project_id, api_key = create_project("-pattern")

        create_policy(project_id, api_key, [
            {
                "action_type": "send_email",
                "constraints": {
                    "params.recipient": {"pattern": r"^[a-zA-Z0-9._%+-]+@company\.com$"}
                },
                "allowed_agents": ["agent"]
            }
        ])

        # Valid email pattern
        status, result = validate_action(
            project_id, api_key, "agent", "send_email",
            {"recipient": "user@company.com"}
        )
        assert result["allowed"] is True

        # Invalid email pattern (wrong domain)
        status, result = validate_action(
            project_id, api_key, "agent", "send_email",
            {"recipient": "user@external.com"}
        )
        assert result["allowed"] is False
        assert "does not match pattern" in result["reason"]

    def test_multiple_constraints_same_param(
        self, create_project, create_policy, validate_action
    ):
        """Both min and max on same param."""
        project_id, api_key = create_project("-multi-constraint")

        create_policy(project_id, api_key, [
            {
                "action_type": "transfer",
                "constraints": {
                    "params.amount": {"min": 10, "max": 1000}
                },
                "allowed_agents": ["agent"]
            }
        ])

        # Below min
        status, result = validate_action(
            project_id, api_key, "agent", "transfer", {"amount": 5}
        )
        assert result["allowed"] is False
        assert "below minimum" in result["reason"]

        # Above max
        status, result = validate_action(
            project_id, api_key, "agent", "transfer", {"amount": 2000}
        )
        assert result["allowed"] is False
        assert "exceeds maximum" in result["reason"]

        # In valid range
        status, result = validate_action(
            project_id, api_key, "agent", "transfer", {"amount": 500}
        )
        assert result["allowed"] is True

    def test_in_constraint_empty_list(
        self, create_project, create_policy, validate_action
    ):
        """Constraint {'in': []} blocks everything."""
        project_id, api_key = create_project("-empty-in")

        create_policy(project_id, api_key, [
            {
                "action_type": "action",
                "constraints": {
                    "params.status": {"in": []}  # Empty whitelist
                },
                "allowed_agents": ["agent"]
            }
        ])

        # No value can match empty list
        for status_value in ["active", "pending", "complete", ""]:
            status, result = validate_action(
                project_id, api_key, "agent", "action", {"status": status_value}
            )
            assert result["allowed"] is False
            assert "not in allowed values" in result["reason"]

    def test_allowed_agents_empty_list_allows_all(
        self, create_project, create_policy, validate_action
    ):
        """Empty allowed_agents list is treated as 'no restriction' (allows all)."""
        project_id, api_key = create_project("-empty-agents")

        # Empty allowed_agents means no agent restriction (falsy check)
        create_policy(project_id, api_key, [
            {
                "action_type": "open_action",
                "allowed_agents": []  # Empty = no restriction
            }
        ], default="allow")

        # All agents can perform this action
        for agent in ["admin", "user", "system", "root"]:
            status, result = validate_action(
                project_id, api_key, agent, "open_action", {}
            )
            assert result["allowed"] is True

    def test_allowed_agents_restricts_access(
        self, create_project, create_policy, validate_action
    ):
        """Non-empty allowed_agents list restricts to listed agents only."""
        project_id, api_key = create_project("-restricted-agents")

        create_policy(project_id, api_key, [
            {
                "action_type": "restricted_action",
                "allowed_agents": ["admin"]  # Only admin allowed
            }
        ])

        # Admin can perform the action
        status, result = validate_action(
            project_id, api_key, "admin", "restricted_action", {}
        )
        assert result["allowed"] is True

        # Other agents cannot
        for agent in ["user", "system", "root"]:
            status, result = validate_action(
                project_id, api_key, agent, "restricted_action", {}
            )
            assert result["allowed"] is False
            assert "not in allowed agents" in result["reason"]
