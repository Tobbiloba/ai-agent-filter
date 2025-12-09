"""E2E tests for multiple projects and agents scenarios.

Tests isolation between projects, multiple agents, and cross-project access control.
"""

from concurrent.futures import ThreadPoolExecutor

import pytest


class TestMultiProject:
    """E2E tests for multiple projects and agent isolation."""

    def test_create_multiple_independent_projects(self, client, create_project, create_policy):
        """Create 3 projects with different policies."""
        projects = []

        # Project 1: Finance - strict limits
        p1_id, p1_key = create_project("-finance")
        create_policy(p1_id, p1_key, [
            {
                "action_type": "transfer",
                "constraints": {"params.amount": {"max": 1000}},
                "allowed_agents": ["finance_bot"]
            }
        ])
        projects.append((p1_id, p1_key))

        # Project 2: Marketing - allow all
        p2_id, p2_key = create_project("-marketing")
        create_policy(p2_id, p2_key, [
            {"action_type": "*", "allowed_agents": ["marketing_bot"]}
        ], default="allow")
        projects.append((p2_id, p2_key))

        # Project 3: Support - block by default
        p3_id, p3_key = create_project("-support")
        create_policy(p3_id, p3_key, [
            {"action_type": "respond_ticket", "allowed_agents": ["support_bot"]}
        ], default="block")
        projects.append((p3_id, p3_key))

        # Verify all projects exist
        for project_id, _ in projects:
            response = client.get(f"/projects/{project_id}")
            assert response.status_code == 200
            assert response.json()["is_active"] is True

    def test_project_isolation_api_keys(
        self, client, create_project, create_policy, validate_action
    ):
        """Project A's API key cannot access project B."""
        # Create two projects
        project_a, key_a = create_project("-proj-a")
        project_b, key_b = create_project("-proj-b")

        create_policy(project_a, key_a, [{"action_type": "*", "allowed_agents": ["agent"]}])
        create_policy(project_b, key_b, [{"action_type": "*", "allowed_agents": ["agent"]}])

        # Try to validate action on project_b using project_a's key
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_b,
                "agent_name": "agent",
                "action_type": "test",
                "params": {}
            },
            headers={"X-API-Key": key_a}
        )
        assert response.status_code == 403
        # Error message indicates key mismatch
        assert "API key" in response.json()["detail"]

    def test_each_project_has_own_logs(
        self, create_project, create_policy, validate_action, get_logs
    ):
        """Logs are isolated per project."""
        # Create two projects
        project_a, key_a = create_project("-logs-a")
        project_b, key_b = create_project("-logs-b")

        create_policy(project_a, key_a, [{"action_type": "*", "allowed_agents": ["agent"]}])
        create_policy(project_b, key_b, [{"action_type": "*", "allowed_agents": ["agent"]}])

        # Validate actions on each project
        validate_action(project_a, key_a, "agent", "action_a", {"source": "project_a"})
        validate_action(project_b, key_b, "agent", "action_b", {"source": "project_b"})

        # Check logs are isolated
        logs_a = get_logs(project_a, key_a)
        logs_b = get_logs(project_b, key_b)

        assert len(logs_a["items"]) == 1
        assert logs_a["items"][0]["action_type"] == "action_a"

        assert len(logs_b["items"]) == 1
        assert logs_b["items"][0]["action_type"] == "action_b"

    def test_each_project_has_own_stats(
        self, create_project, create_policy, validate_action, get_stats
    ):
        """Stats are isolated per project."""
        # Create two projects with different block rates
        project_a, key_a = create_project("-stats-a")
        project_b, key_b = create_project("-stats-b")

        create_policy(project_a, key_a, [
            {"action_type": "allowed", "allowed_agents": ["agent"]},
            {"action_type": "blocked", "blocked_agents": ["agent"]}
        ])
        create_policy(project_b, key_b, [
            {"action_type": "*", "allowed_agents": ["agent"]}
        ], default="allow")

        # Project A: 1 allowed, 1 blocked
        validate_action(project_a, key_a, "agent", "allowed", {})
        validate_action(project_a, key_a, "agent", "blocked", {})

        # Project B: 3 allowed
        for i in range(3):
            validate_action(project_b, key_b, "agent", f"action_{i}", {})

        stats_a = get_stats(project_a, key_a)
        stats_b = get_stats(project_b, key_b)

        assert stats_a["total_actions"] == 2
        assert stats_a["allowed"] == 1
        assert stats_a["blocked"] == 1

        assert stats_b["total_actions"] == 3
        assert stats_b["allowed"] == 3
        assert stats_b["blocked"] == 0

    def test_multiple_agents_same_project(
        self, create_project, create_policy, validate_action, get_logs
    ):
        """Multiple agents validate against the same policy."""
        project_id, api_key = create_project("-multi-agent")

        create_policy(project_id, api_key, [
            {
                "action_type": "process_order",
                "allowed_agents": ["order_agent", "fulfillment_agent", "billing_agent"]
            }
        ])

        agents = ["order_agent", "fulfillment_agent", "billing_agent"]
        for agent in agents:
            status, result = validate_action(
                project_id, api_key, agent, "process_order", {"agent": agent}
            )
            assert result["allowed"] is True

        logs = get_logs(project_id, api_key)
        logged_agents = {item["agent_name"] for item in logs["items"]}
        assert logged_agents == set(agents)

    def test_agent_allowed_in_one_blocked_in_another(
        self, create_project, create_policy, validate_action
    ):
        """Same action allowed/blocked based on project policy."""
        # Project with strict policy
        strict_id, strict_key = create_project("-strict")
        create_policy(strict_id, strict_key, [
            {"action_type": "send_email", "allowed_agents": ["verified_agent"]}
        ])

        # Project with permissive policy
        permissive_id, permissive_key = create_project("-permissive")
        create_policy(permissive_id, permissive_key, [
            {"action_type": "*", "allowed_agents": ["any_agent", "unverified_agent"]}
        ], default="allow")

        # Unverified agent blocked in strict project
        status, result = validate_action(
            strict_id, strict_key, "unverified_agent", "send_email", {}
        )
        assert result["allowed"] is False

        # Same agent allowed in permissive project
        status, result = validate_action(
            permissive_id, permissive_key, "unverified_agent", "send_email", {}
        )
        assert result["allowed"] is True

    def test_rate_limits_keyed_by_agent_and_action(
        self, create_project, create_policy, validate_action
    ):
        """Rate limits are keyed by agent:action_type combination."""
        # Note: PolicyEngine is a singleton, rate limits persist across tests
        # Rate limit key is "{agent_name}:{action_type}" - not project-scoped
        project_id, api_key = create_project("-rate-key")

        create_policy(project_id, api_key, [
            {
                "action_type": "limited_action",
                "allowed_agents": ["agent_x", "agent_y"],
                "rate_limit": {"max_requests": 2, "window_seconds": 60}
            }
        ])

        # agent_x uses its limit
        validate_action(project_id, api_key, "agent_x", "limited_action", {"i": 1})
        validate_action(project_id, api_key, "agent_x", "limited_action", {"i": 2})

        # agent_x is now rate limited
        status, result = validate_action(
            project_id, api_key, "agent_x", "limited_action", {"i": 3}
        )
        assert result["allowed"] is False
        assert "Rate limit exceeded" in result["reason"]

        # agent_y has its own limit and is not affected
        status, result = validate_action(
            project_id, api_key, "agent_y", "limited_action", {"i": 1}
        )
        assert result["allowed"] is True

    def test_concurrent_validations_different_projects(
        self, client, create_project, create_policy
    ):
        """Parallel validations across projects work correctly."""
        # Create 3 projects
        projects = []
        for i in range(3):
            project_id, api_key = create_project(f"-concurrent-{i}")
            create_policy(project_id, api_key, [
                {"action_type": "*", "allowed_agents": ["agent"]}
            ], default="allow")
            projects.append((project_id, api_key))

        def validate(project_id, api_key, index):
            response = client.post(
                "/validate_action",
                json={
                    "project_id": project_id,
                    "agent_name": "agent",
                    "action_type": "concurrent_action",
                    "params": {"index": index}
                },
                headers={"X-API-Key": api_key}
            )
            return response.status_code, response.json()

        # Run 30 validations concurrently across 3 projects
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(30):
                project_id, api_key = projects[i % 3]
                futures.append(executor.submit(validate, project_id, api_key, i))

            results = [f.result() for f in futures]

        # All should succeed
        assert all(status == 200 for status, _ in results)
        assert all(result["allowed"] is True for _, result in results)

    def test_delete_one_project_others_unaffected(
        self, client, create_project, create_policy, validate_action
    ):
        """Deactivating one project doesn't affect others."""
        # Create two projects
        project_a, key_a = create_project("-delete-a")
        project_b, key_b = create_project("-delete-b")

        create_policy(project_a, key_a, [{"action_type": "*", "allowed_agents": ["agent"]}])
        create_policy(project_b, key_b, [{"action_type": "*", "allowed_agents": ["agent"]}])

        # Verify both work
        status, result = validate_action(project_a, key_a, "agent", "test", {})
        assert result["allowed"] is True

        status, result = validate_action(project_b, key_b, "agent", "test", {})
        assert result["allowed"] is True

        # Deactivate project A
        response = client.delete(f"/projects/{project_a}")
        assert response.status_code == 200

        # Project A should fail
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_a,
                "agent_name": "agent",
                "action_type": "test",
                "params": {}
            },
            headers={"X-API-Key": key_a}
        )
        assert response.status_code == 403

        # Project B should still work
        status, result = validate_action(project_b, key_b, "agent", "test", {})
        assert result["allowed"] is True
