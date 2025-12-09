"""E2E tests for policy updates mid-flow.

Tests policy versioning, updates during active validation, and version tracking.
"""

import pytest


class TestPolicyUpdates:
    """E2E tests for policy versioning and mid-flow updates."""

    def test_policy_update_changes_validation_result(
        self, create_project, create_policy, validate_action
    ):
        """Action blocked then allowed after policy change."""
        project_id, api_key = create_project("-update-result")

        # Initial policy: max 100
        create_policy(project_id, api_key, [
            {
                "action_type": "transfer",
                "constraints": {"params.amount": {"max": 100}},
                "allowed_agents": ["agent"]
            }
        ], version="1.0")

        # Amount 150 should be blocked
        status, result = validate_action(
            project_id, api_key, "agent", "transfer", {"amount": 150}
        )
        assert result["allowed"] is False
        assert "exceeds maximum" in result["reason"]

        # Update policy: max 200
        create_policy(project_id, api_key, [
            {
                "action_type": "transfer",
                "constraints": {"params.amount": {"max": 200}},
                "allowed_agents": ["agent"]
            }
        ], version="2.0")

        # Same amount 150 should now be allowed
        status, result = validate_action(
            project_id, api_key, "agent", "transfer", {"amount": 150}
        )
        assert result["allowed"] is True

    def test_logs_show_different_policy_versions(
        self, create_project, create_policy, validate_action, get_logs
    ):
        """Before/after logs show different policy versions."""
        project_id, api_key = create_project("-version-logs")

        # Version 1.0
        create_policy(project_id, api_key, [
            {"action_type": "test", "allowed_agents": ["agent"]}
        ], version="1.0")

        status, result1 = validate_action(
            project_id, api_key, "agent", "test", {"version": "v1"}
        )
        action_id_v1 = result1["action_id"]

        # Version 2.0
        create_policy(project_id, api_key, [
            {"action_type": "test", "allowed_agents": ["agent"]}
        ], version="2.0")

        status, result2 = validate_action(
            project_id, api_key, "agent", "test", {"version": "v2"}
        )
        action_id_v2 = result2["action_id"]

        logs = get_logs(project_id, api_key)

        log_v1 = next(
            (item for item in logs["items"] if item["action_id"] == action_id_v1),
            None
        )
        log_v2 = next(
            (item for item in logs["items"] if item["action_id"] == action_id_v2),
            None
        )

        assert log_v1["policy_version"] == "1.0"
        assert log_v2["policy_version"] == "2.0"

    def test_policy_history_contains_all_versions(
        self, client, create_project, create_policy
    ):
        """GET /policies/{id}/history shows all versions."""
        project_id, api_key = create_project("-history")

        # Create 3 policy versions
        for version in ["1.0", "1.1", "2.0"]:
            create_policy(project_id, api_key, [
                {"action_type": "test", "allowed_agents": ["agent"]}
            ], version=version)

        response = client.get(
            f"/policies/{project_id}/history",
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200

        history = response.json()
        versions = [p["version"] for p in history]

        assert "1.0" in versions
        assert "1.1" in versions
        assert "2.0" in versions

    def test_validation_uses_active_policy_only(
        self, client, create_project, create_policy, validate_action
    ):
        """Only the active policy is used for validation."""
        project_id, api_key = create_project("-active-only")

        # Version 1: allow amounts up to 100
        create_policy(project_id, api_key, [
            {
                "action_type": "spend",
                "constraints": {"params.amount": {"max": 100}},
                "allowed_agents": ["agent"]
            }
        ], version="1.0")

        # Version 2: allow amounts up to 500
        create_policy(project_id, api_key, [
            {
                "action_type": "spend",
                "constraints": {"params.amount": {"max": 500}},
                "allowed_agents": ["agent"]
            }
        ], version="2.0")

        # Amount 200 should be allowed (active policy allows up to 500)
        status, result = validate_action(
            project_id, api_key, "agent", "spend", {"amount": 200}
        )
        assert result["allowed"] is True

        # Check active policy is version 2.0
        response = client.get(
            f"/policies/{project_id}",
            headers={"X-API-Key": api_key}
        )
        assert response.json()["version"] == "2.0"

    def test_rapid_policy_updates_consistent(
        self, create_project, create_policy, validate_action
    ):
        """Multiple rapid updates maintain consistency."""
        project_id, api_key = create_project("-rapid")

        # Rapidly update policy 10 times
        for i in range(10):
            max_val = (i + 1) * 100
            create_policy(project_id, api_key, [
                {
                    "action_type": "test",
                    "constraints": {"params.value": {"max": max_val}},
                    "allowed_agents": ["agent"]
                }
            ], version=f"{i + 1}.0")

        # Final policy has max=1000
        status, result = validate_action(
            project_id, api_key, "agent", "test", {"value": 999}
        )
        assert result["allowed"] is True

        status, result = validate_action(
            project_id, api_key, "agent", "test", {"value": 1001}
        )
        assert result["allowed"] is False

    def test_rollback_policy_by_creating_new(
        self, create_project, create_policy, validate_action
    ):
        """Can 'rollback' by creating policy matching old rules."""
        project_id, api_key = create_project("-rollback")

        # Original strict policy
        strict_rules = [
            {
                "action_type": "sensitive_action",
                "constraints": {"params.amount": {"max": 50}},
                "allowed_agents": ["trusted_agent"]
            }
        ]
        create_policy(project_id, api_key, strict_rules, version="1.0")

        # Permissive policy (oops, too loose!)
        permissive_rules = [
            {
                "action_type": "sensitive_action",
                "constraints": {"params.amount": {"max": 10000}},
                "allowed_agents": ["trusted_agent", "any_agent"]
            }
        ]
        create_policy(project_id, api_key, permissive_rules, version="2.0")

        # This should be allowed with permissive policy
        status, result = validate_action(
            project_id, api_key, "any_agent", "sensitive_action", {"amount": 5000}
        )
        assert result["allowed"] is True

        # Rollback: recreate strict policy
        create_policy(project_id, api_key, strict_rules, version="3.0")

        # Now should be blocked
        status, result = validate_action(
            project_id, api_key, "any_agent", "sensitive_action", {"amount": 5000}
        )
        assert result["allowed"] is False

    def test_constraint_change_reflected_immediately(
        self, create_project, create_policy, validate_action
    ):
        """Changed constraint (max: 500 -> 1000) works immediately."""
        project_id, api_key = create_project("-constraint")

        # Initial: max 500
        create_policy(project_id, api_key, [
            {
                "action_type": "purchase",
                "constraints": {"params.amount": {"max": 500}},
                "allowed_agents": ["buyer"]
            }
        ], version="1.0")

        status, result = validate_action(
            project_id, api_key, "buyer", "purchase", {"amount": 750}
        )
        assert result["allowed"] is False

        # Update: max 1000
        create_policy(project_id, api_key, [
            {
                "action_type": "purchase",
                "constraints": {"params.amount": {"max": 1000}},
                "allowed_agents": ["buyer"]
            }
        ], version="1.1")

        # Immediately takes effect
        status, result = validate_action(
            project_id, api_key, "buyer", "purchase", {"amount": 750}
        )
        assert result["allowed"] is True

    def test_agent_authorization_change(
        self, create_project, create_policy, validate_action
    ):
        """Add/remove agent from allowed_agents."""
        project_id, api_key = create_project("-agent-auth")

        # Initially only agent_a allowed
        create_policy(project_id, api_key, [
            {"action_type": "action", "allowed_agents": ["agent_a"]}
        ], version="1.0")

        status, result = validate_action(
            project_id, api_key, "agent_b", "action", {}
        )
        assert result["allowed"] is False

        # Add agent_b to allowed list
        create_policy(project_id, api_key, [
            {"action_type": "action", "allowed_agents": ["agent_a", "agent_b"]}
        ], version="2.0")

        status, result = validate_action(
            project_id, api_key, "agent_b", "action", {}
        )
        assert result["allowed"] is True

        # Remove agent_a from allowed list
        create_policy(project_id, api_key, [
            {"action_type": "action", "allowed_agents": ["agent_b"]}
        ], version="3.0")

        status, result = validate_action(
            project_id, api_key, "agent_a", "action", {}
        )
        assert result["allowed"] is False

    def test_rate_limit_change_mid_flow(
        self, create_project, create_policy, validate_action
    ):
        """Rate limit changes take effect on new policy."""
        project_id, api_key = create_project("-rate-change")

        # Initial rate limit: 2 per minute
        create_policy(project_id, api_key, [
            {
                "action_type": "api_call",
                "allowed_agents": ["agent"],
                "rate_limit": {"max_requests": 2, "window_seconds": 60}
            }
        ], version="1.0")

        # Use up the limit
        validate_action(project_id, api_key, "agent", "api_call", {"i": 1})
        validate_action(project_id, api_key, "agent", "api_call", {"i": 2})

        status, result = validate_action(
            project_id, api_key, "agent", "api_call", {"i": 3}
        )
        assert result["allowed"] is False
        assert "Rate limit exceeded" in result["reason"]

        # Increase rate limit: 10 per minute
        # Note: rate limit counters are tracked by PolicyEngine which persists across policy updates
        create_policy(project_id, api_key, [
            {
                "action_type": "api_call",
                "allowed_agents": ["agent"],
                "rate_limit": {"max_requests": 10, "window_seconds": 60}
            }
        ], version="2.0")

        # Now should be allowed (new higher limit)
        status, result = validate_action(
            project_id, api_key, "agent", "api_call", {"i": 4}
        )
        assert result["allowed"] is True

    def test_default_behavior_change(
        self, create_project, create_policy, validate_action
    ):
        """Changing default from 'block' to 'allow'."""
        project_id, api_key = create_project("-default")

        # Default: block
        create_policy(project_id, api_key, [
            {"action_type": "known_action", "allowed_agents": ["agent"]}
        ], default="block", version="1.0")

        # Unknown action blocked by default
        status, result = validate_action(
            project_id, api_key, "agent", "unknown_action", {}
        )
        assert result["allowed"] is False

        # Change default to allow
        create_policy(project_id, api_key, [
            {"action_type": "known_action", "allowed_agents": ["agent"]}
        ], default="allow", version="2.0")

        # Unknown action now allowed by default
        status, result = validate_action(
            project_id, api_key, "agent", "unknown_action", {}
        )
        assert result["allowed"] is True
