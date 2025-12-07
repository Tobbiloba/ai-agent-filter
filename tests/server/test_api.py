"""
API Integration Tests for AI Firewall.

Tests all HTTP endpoints using FastAPI's TestClient.
Covers:
- Health endpoints
- Project management (CRUD)
- Authentication (API keys)
- Policy management
- Action validation
- Audit logs
- Error handling
"""

import pytest
from fastapi.testclient import TestClient

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from server.app import app


@pytest.fixture
def client():
    """Create a test client with fresh database for each test."""
    # Use TestClient which handles lifespan events
    with TestClient(app) as c:
        yield c


@pytest.fixture
def project_with_key(client):
    """Create a project and return (project_id, api_key)."""
    import time
    project_id = f"test-project-{int(time.time() * 1000)}"
    response = client.post("/projects", json={
        "id": project_id,
        "name": "Test Project"
    })
    assert response.status_code == 200
    data = response.json()
    return data["id"], data["api_key"]


@pytest.fixture
def project_with_policy(client, project_with_key):
    """Create a project with a policy configured."""
    project_id, api_key = project_with_key

    # Create a policy
    policy = {
        "name": "test-policy",
        "version": "1.0",
        "default": "block",
        "rules": [
            {
                "action_type": "test_action",
                "constraints": {
                    "params.amount": {"max": 100}
                },
                "allowed_agents": ["test_agent"]
            }
        ]
    }
    response = client.post(
        f"/policies/{project_id}",
        json=policy,
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 200

    return project_id, api_key


# =============================================================================
# HEALTH & ROOT ENDPOINT TESTS
# =============================================================================

class TestHealthEndpoints:
    """Tests for health and root endpoints."""

    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_status_healthy(self, client):
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_returns_version(self, client):
        response = client.get("/health")
        data = response.json()
        assert "version" in data
        assert data["version"] == "0.1.0"

    def test_root_returns_api_info(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data


# =============================================================================
# PROJECT MANAGEMENT TESTS
# =============================================================================

class TestProjectManagement:
    """Tests for /projects endpoints."""

    def test_create_project_success(self, client):
        import time
        project_id = f"new-project-{int(time.time() * 1000)}"
        response = client.post("/projects", json={
            "id": project_id,
            "name": "New Project"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == project_id
        assert data["name"] == "New Project"

    def test_create_project_returns_api_key(self, client):
        import time
        project_id = f"key-test-{int(time.time() * 1000)}"
        response = client.post("/projects", json={
            "id": project_id,
            "name": "Key Test"
        })
        data = response.json()
        assert "api_key" in data
        assert data["api_key"].startswith("af_")
        assert len(data["api_key"]) > 20

    def test_create_duplicate_project_returns_409(self, client, project_with_key):
        project_id, _ = project_with_key
        response = client.post("/projects", json={
            "id": project_id,
            "name": "Duplicate"
        })
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_get_project_success(self, client, project_with_key):
        project_id, _ = project_with_key
        response = client.get(f"/projects/{project_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == project_id
        assert "api_key_preview" in data  # Should have preview, not full key

    def test_get_nonexistent_project_returns_404(self, client):
        response = client.get("/projects/nonexistent-project-xyz")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_delete_project_success(self, client, project_with_key):
        project_id, _ = project_with_key
        response = client.delete(f"/projects/{project_id}")
        assert response.status_code == 200
        assert "deactivated" in response.json()["message"]

    def test_delete_nonexistent_project_returns_404(self, client):
        response = client.delete("/projects/nonexistent-project-xyz")
        assert response.status_code == 404

    def test_project_is_active_by_default(self, client, project_with_key):
        project_id, _ = project_with_key
        response = client.get(f"/projects/{project_id}")
        data = response.json()
        assert data["is_active"] is True


# =============================================================================
# AUTHENTICATION TESTS
# =============================================================================

class TestAuthentication:
    """Tests for API key authentication."""

    def test_request_without_api_key_returns_401(self, client, project_with_key):
        project_id, _ = project_with_key
        response = client.get(f"/policies/{project_id}")
        assert response.status_code == 401
        assert "Missing API key" in response.json()["detail"]

    def test_request_with_invalid_api_key_returns_403(self, client, project_with_key):
        project_id, _ = project_with_key
        response = client.get(
            f"/policies/{project_id}",
            headers={"X-API-Key": "invalid-key-12345"}
        )
        assert response.status_code == 403

    def test_request_with_valid_api_key_succeeds(self, client, project_with_policy):
        project_id, api_key = project_with_policy
        response = client.get(
            f"/policies/{project_id}",
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200

    def test_api_key_for_wrong_project_returns_403(self, client):
        """API key for project A should not access project B."""
        import time

        # Create project A
        response = client.post("/projects", json={
            "id": f"project-a-{int(time.time() * 1000)}",
            "name": "Project A"
        })
        project_a_id = response.json()["id"]
        project_a_key = response.json()["api_key"]

        # Create project B
        response = client.post("/projects", json={
            "id": f"project-b-{int(time.time() * 1000)}",
            "name": "Project B"
        })
        project_b_id = response.json()["id"]

        # Try to access project B with project A's key
        response = client.get(
            f"/policies/{project_b_id}",
            headers={"X-API-Key": project_a_key}
        )
        assert response.status_code == 403

    def test_deactivated_project_api_key_fails(self, client, project_with_policy):
        project_id, api_key = project_with_policy

        # Deactivate the project
        client.delete(f"/projects/{project_id}")

        # Try to use the API key
        response = client.get(
            f"/policies/{project_id}",
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 403


# =============================================================================
# POLICY MANAGEMENT TESTS
# =============================================================================

class TestPolicyManagement:
    """Tests for /policies endpoints."""

    def test_create_policy_success(self, client, project_with_key):
        project_id, api_key = project_with_key
        policy = {
            "name": "my-policy",
            "version": "1.0",
            "default": "block",
            "rules": []
        }
        response = client.post(
            f"/policies/{project_id}",
            json=policy,
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "my-policy"
        assert data["is_active"] is True

    def test_get_policy_success(self, client, project_with_policy):
        project_id, api_key = project_with_policy
        response = client.get(
            f"/policies/{project_id}",
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        data = response.json()
        assert "rules" in data
        assert data["project_id"] == project_id

    def test_get_policy_without_auth_returns_401(self, client, project_with_policy):
        project_id, _ = project_with_policy
        response = client.get(f"/policies/{project_id}")
        assert response.status_code == 401

    def test_get_policy_no_policy_returns_404(self, client, project_with_key):
        """Project exists but has no policy configured."""
        project_id, api_key = project_with_key
        response = client.get(
            f"/policies/{project_id}",
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 404
        assert "No active policy" in response.json()["detail"]

    def test_update_policy_deactivates_old(self, client, project_with_policy):
        project_id, api_key = project_with_policy

        # Create a new policy (v2)
        new_policy = {
            "name": "updated-policy",
            "version": "2.0",
            "default": "allow",
            "rules": []
        }
        response = client.post(
            f"/policies/{project_id}",
            json=new_policy,
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200

        # Get active policy - should be v2
        response = client.get(
            f"/policies/{project_id}",
            headers={"X-API-Key": api_key}
        )
        data = response.json()
        assert data["version"] == "2.0"
        assert data["name"] == "updated-policy"

    def test_policy_history(self, client, project_with_policy):
        project_id, api_key = project_with_policy

        # Create another policy version
        client.post(
            f"/policies/{project_id}",
            json={"name": "v2", "version": "2.0", "default": "allow", "rules": []},
            headers={"X-API-Key": api_key}
        )

        # Get history
        response = client.get(
            f"/policies/{project_id}/history",
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2  # At least 2 versions

    def test_policy_with_rules(self, client, project_with_key):
        project_id, api_key = project_with_key
        policy = {
            "name": "rules-policy",
            "version": "1.0",
            "default": "block",
            "rules": [
                {
                    "action_type": "pay_invoice",
                    "constraints": {
                        "params.amount": {"max": 500, "min": 1}
                    },
                    "allowed_agents": ["finance_agent"],
                    "rate_limit": {"max_requests": 10, "window_seconds": 60}
                }
            ]
        }
        response = client.post(
            f"/policies/{project_id}",
            json=policy,
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["rules"]["rules"]) == 1


# =============================================================================
# ACTION VALIDATION TESTS
# =============================================================================

class TestActionValidation:
    """Tests for /validate_action endpoint."""

    def test_validate_allowed_action(self, client, project_with_policy):
        project_id, api_key = project_with_policy
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "test_agent",
                "action_type": "test_action",
                "params": {"amount": 50}
            },
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] is True
        assert "action_id" in data

    def test_validate_blocked_action_exceeds_max(self, client, project_with_policy):
        project_id, api_key = project_with_policy
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "test_agent",
                "action_type": "test_action",
                "params": {"amount": 200}  # Exceeds max of 100
            },
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] is False
        assert "exceeds maximum" in data["reason"]

    def test_validate_blocked_action_wrong_agent(self, client, project_with_policy):
        project_id, api_key = project_with_policy
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "unauthorized_agent",  # Not in allowed_agents
                "action_type": "test_action",
                "params": {"amount": 50}
            },
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] is False
        assert "not in allowed agents" in data["reason"]

    def test_validate_without_api_key_returns_401(self, client, project_with_policy):
        project_id, _ = project_with_policy
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "test_agent",
                "action_type": "test_action",
                "params": {}
            }
        )
        assert response.status_code == 401

    def test_validate_wrong_project_id_returns_403(self, client, project_with_policy):
        _, api_key = project_with_policy
        response = client.post(
            "/validate_action",
            json={
                "project_id": "different-project",  # Wrong project ID
                "agent_name": "test_agent",
                "action_type": "test_action",
                "params": {}
            },
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 403

    def test_validate_returns_action_id(self, client, project_with_policy):
        project_id, api_key = project_with_policy
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "test_agent",
                "action_type": "test_action",
                "params": {"amount": 50}
            },
            headers={"X-API-Key": api_key}
        )
        data = response.json()
        assert "action_id" in data
        assert data["action_id"].startswith("act_")

    def test_validate_returns_timestamp(self, client, project_with_policy):
        project_id, api_key = project_with_policy
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "test_agent",
                "action_type": "test_action",
                "params": {}
            },
            headers={"X-API-Key": api_key}
        )
        data = response.json()
        assert "timestamp" in data

    def test_validate_unknown_action_with_default_block(self, client, project_with_policy):
        """Actions not matching any rule should use default policy."""
        project_id, api_key = project_with_policy
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "test_agent",
                "action_type": "unknown_action",  # No rule for this
                "params": {}
            },
            headers={"X-API-Key": api_key}
        )
        data = response.json()
        assert data["allowed"] is False  # Default is block


# =============================================================================
# AUDIT LOG TESTS
# =============================================================================

class TestAuditLogs:
    """Tests for /logs endpoints."""

    def test_get_logs_success(self, client, project_with_policy):
        project_id, api_key = project_with_policy

        # Perform an action to generate a log
        client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "test_agent",
                "action_type": "test_action",
                "params": {"amount": 50}
            },
            headers={"X-API-Key": api_key}
        )

        # Get logs
        response = client.get(
            f"/logs/{project_id}",
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) >= 1

    def test_get_logs_pagination(self, client, project_with_policy):
        project_id, api_key = project_with_policy

        # Perform multiple actions
        for i in range(5):
            client.post(
                "/validate_action",
                json={
                    "project_id": project_id,
                    "agent_name": "test_agent",
                    "action_type": "test_action",
                    "params": {"amount": i}
                },
                headers={"X-API-Key": api_key}
            )

        # Get first page with small page size
        response = client.get(
            f"/logs/{project_id}?page=1&page_size=2",
            headers={"X-API-Key": api_key}
        )
        data = response.json()
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["has_more"] is True

    def test_get_logs_filter_by_agent(self, client, project_with_policy):
        project_id, api_key = project_with_policy

        # Create actions from different agents
        client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "agent_a",
                "action_type": "test_action",
                "params": {"amount": 50}
            },
            headers={"X-API-Key": api_key}
        )
        client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "agent_b",
                "action_type": "test_action",
                "params": {"amount": 50}
            },
            headers={"X-API-Key": api_key}
        )

        # Filter by agent_a
        response = client.get(
            f"/logs/{project_id}?agent_name=agent_a",
            headers={"X-API-Key": api_key}
        )
        data = response.json()
        for item in data["items"]:
            assert item["agent_name"] == "agent_a"

    def test_get_logs_filter_by_allowed(self, client, project_with_policy):
        project_id, api_key = project_with_policy

        # Create allowed action
        client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "test_agent",
                "action_type": "test_action",
                "params": {"amount": 50}
            },
            headers={"X-API-Key": api_key}
        )
        # Create blocked action
        client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "test_agent",
                "action_type": "test_action",
                "params": {"amount": 200}  # Exceeds max
            },
            headers={"X-API-Key": api_key}
        )

        # Filter blocked only
        response = client.get(
            f"/logs/{project_id}?allowed=false",
            headers={"X-API-Key": api_key}
        )
        data = response.json()
        for item in data["items"]:
            assert item["allowed"] is False

    def test_get_log_stats(self, client, project_with_policy):
        project_id, api_key = project_with_policy

        # Generate some actions
        client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "test_agent",
                "action_type": "test_action",
                "params": {"amount": 50}
            },
            headers={"X-API-Key": api_key}
        )

        # Get stats
        response = client.get(
            f"/logs/{project_id}/stats",
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_actions" in data
        assert "allowed" in data
        assert "blocked" in data
        assert "block_rate" in data


# =============================================================================
# REQUEST VALIDATION / ERROR HANDLING TESTS
# =============================================================================

class TestRequestValidation:
    """Tests for request validation and error handling."""

    def test_create_project_missing_id_returns_422(self, client):
        response = client.post("/projects", json={
            "name": "Missing ID"
            # Missing "id" field
        })
        assert response.status_code == 422

    def test_create_project_missing_name_returns_422(self, client):
        response = client.post("/projects", json={
            "id": "missing-name-project"
            # Missing "name" field
        })
        assert response.status_code == 422

    def test_validate_action_missing_project_id_returns_422(self, client, project_with_policy):
        _, api_key = project_with_policy
        response = client.post(
            "/validate_action",
            json={
                # Missing project_id
                "agent_name": "test",
                "action_type": "test",
                "params": {}
            },
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 422

    def test_validate_action_missing_agent_name_returns_422(self, client, project_with_policy):
        project_id, api_key = project_with_policy
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                # Missing agent_name
                "action_type": "test",
                "params": {}
            },
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 422

    def test_invalid_json_body_returns_422(self, client, project_with_key):
        project_id, api_key = project_with_key
        response = client.post(
            f"/policies/{project_id}",
            content="not valid json",
            headers={
                "X-API-Key": api_key,
                "Content-Type": "application/json"
            }
        )
        assert response.status_code == 422

    def test_policy_invalid_rule_type_returns_422(self, client, project_with_key):
        project_id, api_key = project_with_key
        response = client.post(
            f"/policies/{project_id}",
            json={
                "name": "test",
                "version": "1.0",
                "default": "block",
                "rules": [
                    {
                        "action_type": 12345,  # Should be string, not int
                        "constraints": "not a dict"  # Should be dict, not string
                    }
                ]
            },
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 422

    def test_pagination_page_size_exceeds_max(self, client, project_with_policy):
        project_id, api_key = project_with_policy
        response = client.get(
            f"/logs/{project_id}?page_size=500",  # Max is 100
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 422

    def test_pagination_negative_page_returns_422(self, client, project_with_policy):
        project_id, api_key = project_with_policy
        response = client.get(
            f"/logs/{project_id}?page=-1",
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 422
