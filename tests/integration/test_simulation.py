"""
Integration tests for policy simulation (what-if mode).

Tests end-to-end simulation behavior via the API.
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
    with TestClient(app) as c:
        yield c


@pytest.fixture
def project_with_policy(client):
    """Create a project with a policy configured."""
    import time
    project_id = f"sim-test-{int(time.time() * 1000)}"

    # Create project
    response = client.post("/projects", json={
        "id": project_id,
        "name": "Simulation Test Project"
    })
    assert response.status_code == 200
    api_key = response.json()["api_key"]

    # Create a policy with constraints
    policy = {
        "name": "sim-test-policy",
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


class TestSimulationAPI:
    """Integration tests for simulation via API."""

    def test_simulation_returns_simulated_true(self, client, project_with_policy):
        """Simulated request should return simulated=True."""
        project_id, api_key = project_with_policy

        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "test_agent",
                "action_type": "test_action",
                "params": {"amount": 50},
                "simulate": True,
            },
            headers={"X-API-Key": api_key}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["simulated"] is True

    def test_simulation_returns_null_action_id(self, client, project_with_policy):
        """Simulated request should return action_id=null."""
        project_id, api_key = project_with_policy

        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "test_agent",
                "action_type": "test_action",
                "params": {"amount": 50},
                "simulate": True,
            },
            headers={"X-API-Key": api_key}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["action_id"] is None

    def test_simulation_does_not_create_log(self, client, project_with_policy):
        """Simulated request should NOT create an audit log entry."""
        project_id, api_key = project_with_policy

        # Get initial log count
        logs_before = client.get(
            f"/logs/{project_id}",
            headers={"X-API-Key": api_key}
        )
        count_before = logs_before.json()["total"]

        # Make a simulated request
        client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "test_agent",
                "action_type": "test_action",
                "params": {"amount": 50},
                "simulate": True,
            },
            headers={"X-API-Key": api_key}
        )

        # Get log count after simulation
        logs_after = client.get(
            f"/logs/{project_id}",
            headers={"X-API-Key": api_key}
        )
        count_after = logs_after.json()["total"]

        # Count should be unchanged
        assert count_after == count_before

    def test_non_simulation_creates_log(self, client, project_with_policy):
        """Non-simulated request SHOULD create an audit log entry."""
        project_id, api_key = project_with_policy

        # Get initial log count
        logs_before = client.get(
            f"/logs/{project_id}",
            headers={"X-API-Key": api_key}
        )
        count_before = logs_before.json()["total"]

        # Make a real (non-simulated) request
        client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "test_agent",
                "action_type": "test_action",
                "params": {"amount": 50},
                "simulate": False,
            },
            headers={"X-API-Key": api_key}
        )

        # Get log count after
        logs_after = client.get(
            f"/logs/{project_id}",
            headers={"X-API-Key": api_key}
        )
        count_after = logs_after.json()["total"]

        # Count should increase by 1
        assert count_after == count_before + 1

    def test_simulation_validates_correctly_allowed(self, client, project_with_policy):
        """Simulation should correctly validate allowed actions."""
        project_id, api_key = project_with_policy

        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "test_agent",
                "action_type": "test_action",
                "params": {"amount": 50},  # Within limit
                "simulate": True,
            },
            headers={"X-API-Key": api_key}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] is True
        assert data["simulated"] is True

    def test_simulation_validates_correctly_blocked(self, client, project_with_policy):
        """Simulation should correctly validate blocked actions."""
        project_id, api_key = project_with_policy

        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "test_agent",
                "action_type": "test_action",
                "params": {"amount": 200},  # Exceeds max of 100
                "simulate": True,
            },
            headers={"X-API-Key": api_key}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] is False
        assert data["simulated"] is True
        assert "exceeds maximum" in data["reason"]

    def test_simulation_default_false(self, client, project_with_policy):
        """simulate parameter should default to false."""
        project_id, api_key = project_with_policy

        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "test_agent",
                "action_type": "test_action",
                "params": {"amount": 50},
                # No simulate parameter
            },
            headers={"X-API-Key": api_key}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["simulated"] is False
        assert data["action_id"] is not None

    def test_multiple_simulations_no_logs(self, client, project_with_policy):
        """Multiple simulations should not create any logs."""
        project_id, api_key = project_with_policy

        # Get initial log count
        logs_before = client.get(
            f"/logs/{project_id}",
            headers={"X-API-Key": api_key}
        )
        count_before = logs_before.json()["total"]

        # Make multiple simulated requests
        for i in range(5):
            client.post(
                "/validate_action",
                json={
                    "project_id": project_id,
                    "agent_name": "test_agent",
                    "action_type": "test_action",
                    "params": {"amount": i * 10},
                    "simulate": True,
                },
                headers={"X-API-Key": api_key}
            )

        # Get log count after
        logs_after = client.get(
            f"/logs/{project_id}",
            headers={"X-API-Key": api_key}
        )
        count_after = logs_after.json()["total"]

        # Count should be unchanged
        assert count_after == count_before

    def test_simulation_with_wrong_agent(self, client, project_with_policy):
        """Simulation should block unauthorized agents."""
        project_id, api_key = project_with_policy

        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "unauthorized_agent",  # Not in allowed_agents
                "action_type": "test_action",
                "params": {"amount": 50},
                "simulate": True,
            },
            headers={"X-API-Key": api_key}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] is False
        assert data["simulated"] is True
        assert "not in allowed agents" in data["reason"]
