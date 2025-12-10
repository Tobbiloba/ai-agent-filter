"""Integration tests for fail-closed mode.

These tests verify end-to-end fail-closed functionality using
the actual server with mocked failures.
"""

import pytest
import time
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from server.app import app
from server.config import Settings


@pytest.fixture
def client():
    """Create TestClient with fresh database for each test."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def unique_id():
    """Generate unique timestamp-based ID for test isolation."""
    return f"fc-{int(time.time() * 1000)}"


@pytest.fixture
def create_project(client, unique_id):
    """Create a test project."""
    response = client.post("/projects", json={
        "id": unique_id,
        "name": "Fail-Closed Test Project"
    })
    assert response.status_code == 200, f"Failed to create project: {response.text}"
    data = response.json()
    return unique_id, data["api_key"]


class TestFailClosedIntegration:
    """Integration tests for fail-closed mode."""

    def test_normal_operation_when_fail_closed_disabled(self, client, create_project):
        """Normal validation should work when fail-closed is disabled."""
        project_id, api_key = create_project

        # Create a simple policy
        client.post(
            f"/policies/{project_id}",
            json={
                "name": "test-policy",
                "version": "1.0",
                "default": "allow",
                "rules": []
            },
            headers={"X-API-Key": api_key}
        )

        # Normal validation should succeed
        with patch("server.routes.validate.get_settings") as mock_settings:
            mock_settings.return_value = Settings(fail_closed=False)

            response = client.post(
                "/validate_action",
                json={
                    "project_id": project_id,
                    "agent_name": "test-agent",
                    "action_type": "test-action",
                    "params": {}
                },
                headers={"X-API-Key": api_key}
            )

            assert response.status_code == 200
            assert response.json()["allowed"] is True

    def test_normal_operation_when_fail_closed_enabled(self, client, create_project):
        """Normal validation should still work when fail-closed is enabled."""
        project_id, api_key = create_project

        # Create a simple policy
        client.post(
            f"/policies/{project_id}",
            json={
                "name": "test-policy",
                "version": "1.0",
                "default": "allow",
                "rules": []
            },
            headers={"X-API-Key": api_key}
        )

        # Normal validation should succeed even with fail-closed enabled
        with patch("server.routes.validate.get_settings") as mock_settings:
            mock_settings.return_value = Settings(fail_closed=True)

            response = client.post(
                "/validate_action",
                json={
                    "project_id": project_id,
                    "agent_name": "test-agent",
                    "action_type": "test-action",
                    "params": {}
                },
                headers={"X-API-Key": api_key}
            )

            assert response.status_code == 200
            assert response.json()["allowed"] is True

    def test_fail_closed_blocks_on_validator_error(self, client, create_project):
        """When fail-closed is enabled, validator errors should return blocked."""
        project_id, api_key = create_project

        with patch("server.routes.validate.get_settings") as mock_settings:
            mock_settings.return_value = Settings(fail_closed=True)

            with patch("server.routes.validate.ValidatorService") as mock_validator:
                mock_validator.return_value.validate_action = AsyncMock(
                    side_effect=Exception("Simulated database error")
                )

                response = client.post(
                    "/validate_action",
                    json={
                        "project_id": project_id,
                        "agent_name": "test-agent",
                        "action_type": "test-action",
                        "params": {}
                    },
                    headers={"X-API-Key": api_key}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["allowed"] is False
                assert "fail-closed" in data["action_id"]
                assert data["reason"] == "Service unavailable - fail-closed mode active"

    def test_fail_open_raises_on_validator_error(self, client, create_project):
        """When fail-closed is disabled, validator errors should raise exception."""
        project_id, api_key = create_project

        with patch("server.routes.validate.get_settings") as mock_settings:
            mock_settings.return_value = Settings(fail_closed=False)

            with patch("server.routes.validate.ValidatorService") as mock_validator:
                mock_validator.return_value.validate_action = AsyncMock(
                    side_effect=Exception("Simulated database error")
                )

                # With fail-closed disabled, errors should propagate as exceptions
                with pytest.raises(Exception, match="Simulated database error"):
                    client.post(
                        "/validate_action",
                        json={
                            "project_id": project_id,
                            "agent_name": "test-agent",
                            "action_type": "test-action",
                            "params": {}
                        },
                        headers={"X-API-Key": api_key}
                    )

    def test_fail_closed_custom_reason(self, client, create_project):
        """Custom fail-closed reason should appear in response."""
        project_id, api_key = create_project
        custom_reason = "Security mode active - contact admin"

        with patch("server.routes.validate.get_settings") as mock_settings:
            mock_settings.return_value = Settings(
                fail_closed=True,
                fail_closed_reason=custom_reason
            )

            with patch("server.routes.validate.ValidatorService") as mock_validator:
                mock_validator.return_value.validate_action = AsyncMock(
                    side_effect=Exception("Error")
                )

                response = client.post(
                    "/validate_action",
                    json={
                        "project_id": project_id,
                        "agent_name": "test-agent",
                        "action_type": "test-action",
                        "params": {}
                    },
                    headers={"X-API-Key": api_key}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["allowed"] is False
                assert data["reason"] == custom_reason

    def test_fail_closed_response_format(self, client, create_project):
        """Fail-closed response should have all required fields."""
        project_id, api_key = create_project

        with patch("server.routes.validate.get_settings") as mock_settings:
            mock_settings.return_value = Settings(fail_closed=True)

            with patch("server.routes.validate.ValidatorService") as mock_validator:
                mock_validator.return_value.validate_action = AsyncMock(
                    side_effect=Exception("Error")
                )

                response = client.post(
                    "/validate_action",
                    json={
                        "project_id": project_id,
                        "agent_name": "test-agent",
                        "action_type": "test-action",
                        "params": {}
                    },
                    headers={"X-API-Key": api_key}
                )

                assert response.status_code == 200
                data = response.json()

                # Verify all expected fields are present
                assert "allowed" in data
                assert "action_id" in data
                assert "timestamp" in data
                assert "reason" in data

                # Verify field values
                assert data["allowed"] is False
                assert data["action_id"].startswith("fail-closed-")
                assert len(data["timestamp"]) > 0  # ISO format timestamp
                assert len(data["reason"]) > 0


class TestFailClosedWithPolicies:
    """Test fail-closed behavior with various policy configurations."""

    def test_fail_closed_overrides_policy_allow(self, client, create_project):
        """Fail-closed should block even if policy would allow."""
        project_id, api_key = create_project

        # Create permissive policy
        client.post(
            f"/policies/{project_id}",
            json={
                "name": "permissive",
                "version": "1.0",
                "default": "allow",
                "rules": []
            },
            headers={"X-API-Key": api_key}
        )

        with patch("server.routes.validate.get_settings") as mock_settings:
            mock_settings.return_value = Settings(fail_closed=True)

            with patch("server.routes.validate.ValidatorService") as mock_validator:
                # Simulate error during validation
                mock_validator.return_value.validate_action = AsyncMock(
                    side_effect=Exception("DB unavailable")
                )

                response = client.post(
                    "/validate_action",
                    json={
                        "project_id": project_id,
                        "agent_name": "test-agent",
                        "action_type": "allowed-action",
                        "params": {}
                    },
                    headers={"X-API-Key": api_key}
                )

                # Should be blocked due to fail-closed, not allowed
                assert response.status_code == 200
                assert response.json()["allowed"] is False


class TestFailClosedSecurityEdgeCases:
    """Test security-related edge cases for fail-closed mode."""

    def test_project_id_mismatch_returns_403_not_fail_closed(self, client, create_project):
        """Project ID mismatch should return 403, not a fail-closed response."""
        project_id, api_key = create_project

        with patch("server.routes.validate.get_settings") as mock_settings:
            mock_settings.return_value = Settings(fail_closed=True)

            # Request with wrong project_id
            response = client.post(
                "/validate_action",
                json={
                    "project_id": "wrong-project-id",
                    "agent_name": "test-agent",
                    "action_type": "test-action",
                    "params": {}
                },
                headers={"X-API-Key": api_key}
            )

            # Should be 403, not a 200 with allowed=false
            assert response.status_code == 403
            # New error format uses {"error": {...}} structure
            error_data = response.json()
            assert "error" in error_data
            assert "project" in error_data["error"]["message"].lower()

    def test_invalid_api_key_returns_403_not_fail_closed(self, client):
        """Invalid API key should return 403, not a fail-closed response."""
        with patch("server.routes.validate.get_settings") as mock_settings:
            mock_settings.return_value = Settings(fail_closed=True)

            response = client.post(
                "/validate_action",
                json={
                    "project_id": "any-project",
                    "agent_name": "test-agent",
                    "action_type": "test-action",
                    "params": {}
                },
                headers={"X-API-Key": "invalid-key-12345"}
            )

            # Should be 403, not a 200 with allowed=false
            assert response.status_code == 403

    def test_missing_api_key_returns_401_not_fail_closed(self, client):
        """Missing API key should return 401, not a fail-closed response."""
        with patch("server.routes.validate.get_settings") as mock_settings:
            mock_settings.return_value = Settings(fail_closed=True)

            response = client.post(
                "/validate_action",
                json={
                    "project_id": "any-project",
                    "agent_name": "test-agent",
                    "action_type": "test-action",
                    "params": {}
                }
                # No X-API-Key header
            )

            # Should be 401, not a 200 with allowed=false
            assert response.status_code == 401
