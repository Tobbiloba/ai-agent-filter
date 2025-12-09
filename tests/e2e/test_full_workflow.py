"""E2E tests for complete workflow scenarios.

Tests the full flow: Create project -> Create policy -> Validate action -> Check logs
"""

import pytest


class TestFullWorkflow:
    """E2E tests for complete workflow from project creation to log verification."""

    def test_complete_workflow_project_to_logs(
        self, client, create_project, create_policy, validate_action, get_logs, get_stats
    ):
        """
        Complete E2E flow:
        1. Create project
        2. Create policy with rules
        3. Validate allowed action
        4. Validate blocked action
        5. Check logs contain both
        6. Check stats reflect counts
        """
        # Step 1: Create project
        project_id, api_key = create_project("-workflow")

        # Step 2: Create policy
        rules = [
            {
                "action_type": "pay_invoice",
                "constraints": {
                    "params.amount": {"max": 100, "min": 1}
                },
                "allowed_agents": ["finance_agent"]
            }
        ]
        response = create_policy(project_id, api_key, rules)
        assert response.status_code == 200

        # Step 3: Validate allowed action
        status, allowed_result = validate_action(
            project_id, api_key, "finance_agent", "pay_invoice", {"amount": 50}
        )
        assert status == 200
        assert allowed_result["allowed"] is True
        allowed_action_id = allowed_result["action_id"]

        # Step 4: Validate blocked action (exceeds max)
        status, blocked_result = validate_action(
            project_id, api_key, "finance_agent", "pay_invoice", {"amount": 200}
        )
        assert status == 200
        assert blocked_result["allowed"] is False
        assert "exceeds maximum" in blocked_result["reason"]
        blocked_action_id = blocked_result["action_id"]

        # Step 5: Check logs contain both
        logs = get_logs(project_id, api_key)
        action_ids = [item["action_id"] for item in logs["items"]]
        assert allowed_action_id in action_ids
        assert blocked_action_id in action_ids

        # Step 6: Check stats
        stats = get_stats(project_id, api_key)
        assert stats["total_actions"] == 2
        assert stats["allowed"] == 1
        assert stats["blocked"] == 1
        assert stats["block_rate"] == 50.0

    def test_allowed_action_appears_in_logs(
        self, create_project, create_policy, validate_action, get_logs
    ):
        """Verify allowed action is logged with correct details."""
        project_id, api_key = create_project("-allowed-logs")

        rules = [
            {
                "action_type": "send_email",
                "allowed_agents": ["email_agent"]
            }
        ]
        create_policy(project_id, api_key, rules)

        status, result = validate_action(
            project_id, api_key, "email_agent", "send_email",
            {"recipient": "test@example.com", "subject": "Hello"}
        )
        assert result["allowed"] is True
        action_id = result["action_id"]

        logs = get_logs(project_id, api_key)
        log_entry = next(
            (item for item in logs["items"] if item["action_id"] == action_id),
            None
        )
        assert log_entry is not None
        assert log_entry["allowed"] is True
        assert log_entry["agent_name"] == "email_agent"
        assert log_entry["action_type"] == "send_email"
        assert log_entry["params"]["recipient"] == "test@example.com"
        assert log_entry["reason"] is None

    def test_blocked_action_appears_in_logs(
        self, create_project, create_policy, validate_action, get_logs
    ):
        """Verify blocked action is logged with reason."""
        project_id, api_key = create_project("-blocked-logs")

        rules = [
            {
                "action_type": "delete_file",
                "allowed_agents": ["admin_agent"]
            }
        ]
        create_policy(project_id, api_key, rules)

        # Use unauthorized agent
        status, result = validate_action(
            project_id, api_key, "guest_agent", "delete_file", {"path": "/etc/passwd"}
        )
        assert result["allowed"] is False
        action_id = result["action_id"]

        logs = get_logs(project_id, api_key)
        log_entry = next(
            (item for item in logs["items"] if item["action_id"] == action_id),
            None
        )
        assert log_entry is not None
        assert log_entry["allowed"] is False
        assert log_entry["agent_name"] == "guest_agent"
        assert log_entry["reason"] is not None
        assert "not in allowed" in log_entry["reason"]

    def test_stats_reflect_validation_results(
        self, create_project, create_policy, validate_action, get_stats
    ):
        """Verify stats show correct allowed/blocked counts."""
        project_id, api_key = create_project("-stats")

        rules = [
            {
                "action_type": "transfer",
                "constraints": {"params.amount": {"max": 100}},
                "allowed_agents": ["agent"]
            }
        ]
        create_policy(project_id, api_key, rules)

        # 3 allowed actions
        for amount in [10, 50, 100]:
            validate_action(project_id, api_key, "agent", "transfer", {"amount": amount})

        # 2 blocked actions
        for amount in [150, 200]:
            validate_action(project_id, api_key, "agent", "transfer", {"amount": amount})

        stats = get_stats(project_id, api_key)
        assert stats["total_actions"] == 5
        assert stats["allowed"] == 3
        assert stats["blocked"] == 2
        assert stats["block_rate"] == 40.0

    def test_multiple_actions_correct_order(
        self, create_project, create_policy, validate_action, get_logs
    ):
        """Multiple validations appear in chronological order in logs."""
        project_id, api_key = create_project("-order")

        rules = [{"action_type": "*", "allowed_agents": ["agent"]}]
        create_policy(project_id, api_key, rules, default="allow")

        action_ids = []
        for i in range(5):
            status, result = validate_action(
                project_id, api_key, "agent", f"action_{i}", {"index": i}
            )
            action_ids.append(result["action_id"])

        logs = get_logs(project_id, api_key)
        logged_ids = [item["action_id"] for item in logs["items"]]

        # Most recent should be first (reverse chronological)
        assert logged_ids == list(reversed(action_ids))

    def test_action_ids_are_unique(
        self, create_project, create_policy, validate_action
    ):
        """Each validation gets unique action_id."""
        project_id, api_key = create_project("-unique-ids")

        rules = [{"action_type": "*", "allowed_agents": ["agent"]}]
        create_policy(project_id, api_key, rules, default="allow")

        action_ids = set()
        for i in range(10):
            status, result = validate_action(
                project_id, api_key, "agent", "test_action", {"iteration": i}
            )
            action_ids.add(result["action_id"])

        assert len(action_ids) == 10, "All action_ids should be unique"

    def test_log_contains_policy_version(
        self, create_project, create_policy, validate_action, get_logs
    ):
        """Logs include the policy version used for validation."""
        project_id, api_key = create_project("-policy-version")

        rules = [{"action_type": "test", "allowed_agents": ["agent"]}]
        create_policy(project_id, api_key, rules, version="2.5.0")

        status, result = validate_action(
            project_id, api_key, "agent", "test", {"data": "value"}
        )
        action_id = result["action_id"]

        logs = get_logs(project_id, api_key)
        log_entry = next(
            (item for item in logs["items"] if item["action_id"] == action_id),
            None
        )
        assert log_entry is not None
        assert log_entry["policy_version"] == "2.5.0"

    def test_execution_time_recorded(
        self, create_project, create_policy, validate_action, get_logs
    ):
        """Logs include execution_time_ms."""
        project_id, api_key = create_project("-exec-time")

        rules = [{"action_type": "test", "allowed_agents": ["agent"]}]
        create_policy(project_id, api_key, rules)

        status, result = validate_action(
            project_id, api_key, "agent", "test", {}
        )
        action_id = result["action_id"]

        # Check response has execution time
        assert "execution_time_ms" in result
        assert result["execution_time_ms"] >= 0

        # Check log entry has execution time
        logs = get_logs(project_id, api_key)
        log_entry = next(
            (item for item in logs["items"] if item["action_id"] == action_id),
            None
        )
        assert log_entry is not None
        assert "execution_time_ms" in log_entry
        assert log_entry["execution_time_ms"] >= 0
