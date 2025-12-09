"""Response Contract Validation Tests.

Validates that all API responses match their declared schemas.
"""

import pytest


class TestResponseContracts:
    """Tests for response format validation."""

    def test_health_response_format(self, client):
        """Health endpoint returns expected structure."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()

        assert isinstance(data.get("status"), str)
        assert isinstance(data.get("version"), str)
        assert data["status"] == "healthy"

    def test_root_response_format(self, client):
        """Root endpoint returns expected structure."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()

        assert "name" in data
        assert "version" in data
        assert "docs" in data
        assert "health" in data
        assert data["name"] == "AI Agent Safety Filter"

    def test_project_create_response_format(self, client):
        """Project creation returns ProjectResponse schema."""
        import time
        project_id = f"contract-create-{int(time.time() * 1000)}"

        response = client.post("/projects", json={
            "id": project_id,
            "name": "Contract Test Project"
        })
        assert response.status_code == 200
        data = response.json()

        # Validate ProjectResponse fields
        assert isinstance(data["id"], str)
        assert data["id"] == project_id
        assert isinstance(data["name"], str)
        assert isinstance(data["api_key"], str)
        assert data["api_key"].startswith("af_")
        assert isinstance(data["is_active"], bool)
        assert data["is_active"] is True
        assert "created_at" in data

    def test_action_allowed_response_format(self, client, create_test_project):
        """ActionResponse for allowed action matches schema."""
        project_id, api_key = create_test_project("-allowed")

        # Create permissive policy
        client.post(
            f"/policies/{project_id}",
            json={"name": "test", "version": "1.0", "default": "allow", "rules": []},
            headers={"X-API-Key": api_key}
        )

        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "test_agent",
                "action_type": "test_action",
                "params": {"key": "value"}
            },
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        data = response.json()

        # Validate ActionResponse fields
        assert isinstance(data["allowed"], bool)
        assert data["allowed"] is True
        assert isinstance(data["action_id"], str)
        assert data["action_id"].startswith("act_")
        assert "timestamp" in data
        assert data.get("reason") is None  # No reason for allowed actions
        assert "execution_time_ms" in data
        assert isinstance(data["execution_time_ms"], int)

    def test_action_blocked_response_format(self, client, create_test_project):
        """ActionResponse for blocked action matches schema."""
        project_id, api_key = create_test_project("-blocked")

        # Create restrictive policy
        client.post(
            f"/policies/{project_id}",
            json={"name": "test", "version": "1.0", "default": "block", "rules": []},
            headers={"X-API-Key": api_key}
        )

        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "test_agent",
                "action_type": "unknown_action",
                "params": {}
            },
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        data = response.json()

        # Validate ActionResponse fields for blocked action
        assert isinstance(data["allowed"], bool)
        assert data["allowed"] is False
        assert isinstance(data["action_id"], str)
        assert "timestamp" in data
        assert isinstance(data.get("reason"), str)  # Has reason when blocked
        assert len(data["reason"]) > 0

    def test_policy_response_format(self, client, create_test_project):
        """PolicyResponse matches schema."""
        project_id, api_key = create_test_project("-policy")

        response = client.post(
            f"/policies/{project_id}",
            json={
                "name": "test-policy",
                "version": "1.0",
                "default": "block",
                "rules": [
                    {"action_type": "test", "allowed_agents": ["agent1"]}
                ]
            },
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        data = response.json()

        # Validate PolicyResponse fields
        assert isinstance(data["id"], int)
        assert isinstance(data["project_id"], str)
        assert data["project_id"] == project_id
        assert isinstance(data["name"], str)
        assert isinstance(data["version"], str)
        assert isinstance(data["rules"], dict)
        assert isinstance(data["is_active"], bool)
        assert data["is_active"] is True
        assert "created_at" in data
        assert "updated_at" in data

    def test_audit_log_list_format(self, client, create_test_project):
        """AuditLogList matches schema."""
        project_id, api_key = create_test_project("-logs")

        # Create policy and perform an action
        client.post(
            f"/policies/{project_id}",
            json={"name": "test", "version": "1.0", "default": "allow", "rules": []},
            headers={"X-API-Key": api_key}
        )
        client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "agent",
                "action_type": "action",
                "params": {}
            },
            headers={"X-API-Key": api_key}
        )

        response = client.get(
            f"/logs/{project_id}",
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        data = response.json()

        # Validate AuditLogList fields
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
        assert isinstance(data["page"], int)
        assert isinstance(data["page_size"], int)
        assert isinstance(data["has_more"], bool)

    def test_audit_log_entry_format(self, client, create_test_project):
        """Individual AuditLogResponse entry matches schema."""
        project_id, api_key = create_test_project("-logentry")

        # Create policy and perform an action
        client.post(
            f"/policies/{project_id}",
            json={"name": "test", "version": "2.0", "default": "allow", "rules": []},
            headers={"X-API-Key": api_key}
        )
        client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "test_agent",
                "action_type": "test_action",
                "params": {"key": "value"}
            },
            headers={"X-API-Key": api_key}
        )

        response = client.get(
            f"/logs/{project_id}",
            headers={"X-API-Key": api_key}
        )
        data = response.json()
        assert len(data["items"]) > 0

        item = data["items"][0]

        # Validate AuditLogResponse fields
        assert isinstance(item["action_id"], str)
        assert item["action_id"].startswith("act_")
        assert isinstance(item["project_id"], str)
        assert item["project_id"] == project_id
        assert isinstance(item["agent_name"], str)
        assert isinstance(item["action_type"], str)
        assert isinstance(item["params"], dict)
        assert isinstance(item["allowed"], bool)
        assert "timestamp" in item
        assert item.get("policy_version") == "2.0"

    def test_stats_response_format(self, client, create_test_project):
        """Stats endpoint returns expected structure."""
        project_id, api_key = create_test_project("-stats")

        # Create policy and perform actions
        client.post(
            f"/policies/{project_id}",
            json={
                "name": "test", "version": "1.0", "default": "block",
                "rules": [{"action_type": "allowed", "allowed_agents": ["agent"]}]
            },
            headers={"X-API-Key": api_key}
        )

        # One allowed, one blocked
        client.post(
            "/validate_action",
            json={"project_id": project_id, "agent_name": "agent",
                  "action_type": "allowed", "params": {}},
            headers={"X-API-Key": api_key}
        )
        client.post(
            "/validate_action",
            json={"project_id": project_id, "agent_name": "agent",
                  "action_type": "blocked", "params": {}},
            headers={"X-API-Key": api_key}
        )

        response = client.get(
            f"/logs/{project_id}/stats",
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        data = response.json()

        # Validate stats fields
        assert isinstance(data["total_actions"], int)
        assert data["total_actions"] == 2
        assert isinstance(data["allowed"], int)
        assert isinstance(data["blocked"], int)
        assert isinstance(data["block_rate"], (int, float))

    def test_error_422_format(self, client):
        """Validation error (422) matches HTTPValidationError schema."""
        response = client.post("/projects", json={})
        assert response.status_code == 422
        data = response.json()

        # Validate HTTPValidationError structure
        assert "detail" in data
        assert isinstance(data["detail"], list)
        for error in data["detail"]:
            assert "loc" in error
            assert "msg" in error
            assert "type" in error

    def test_error_401_format(self, client, create_test_project):
        """401 error has consistent structure."""
        project_id, _ = create_test_project("-auth")

        # Try to access without API key
        response = client.get(f"/policies/{project_id}")
        assert response.status_code == 401
        data = response.json()

        assert "detail" in data
        assert isinstance(data["detail"], str)

    def test_error_404_format(self, client):
        """404 error has consistent structure."""
        response = client.get("/projects/nonexistent-project-xyz-123")
        assert response.status_code == 404
        data = response.json()

        assert "detail" in data
        assert isinstance(data["detail"], str)
