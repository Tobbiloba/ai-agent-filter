"""E2E test fixtures for AI Agent Firewall."""

import time

import pytest
from fastapi.testclient import TestClient

from server.app import app


@pytest.fixture
def client():
    """Create TestClient with fresh database for each test."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def unique_id():
    """Generate unique timestamp-based ID for test isolation."""
    return f"e2e-{int(time.time() * 1000)}"


@pytest.fixture
def create_project(client, unique_id):
    """Factory fixture to create projects.

    Returns a function that creates a project and returns (project_id, api_key).
    """
    def _create(suffix=""):
        project_id = f"{unique_id}{suffix}"
        response = client.post("/projects", json={
            "id": project_id,
            "name": f"E2E Test Project {suffix}"
        })
        assert response.status_code == 200, f"Failed to create project: {response.text}"
        data = response.json()
        return project_id, data["api_key"]
    return _create


@pytest.fixture
def create_policy(client):
    """Factory fixture to create policies for a project.

    Returns a function that creates a policy and returns the response.
    """
    def _create(project_id, api_key, rules, default="block", version="1.0", name="test-policy"):
        response = client.post(
            f"/policies/{project_id}",
            json={
                "name": name,
                "version": version,
                "default": default,
                "rules": rules
            },
            headers={"X-API-Key": api_key}
        )
        return response
    return _create


@pytest.fixture
def validate_action(client):
    """Factory fixture to validate actions.

    Returns a function that validates an action and returns (status_code, response_json).
    """
    def _validate(project_id, api_key, agent_name, action_type, params):
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": agent_name,
                "action_type": action_type,
                "params": params
            },
            headers={"X-API-Key": api_key}
        )
        return response.status_code, response.json()
    return _validate


@pytest.fixture
def get_logs(client):
    """Factory fixture to retrieve audit logs.

    Returns a function that gets logs and returns the response JSON.
    """
    def _get(project_id, api_key, **params):
        response = client.get(
            f"/logs/{project_id}",
            params=params,
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200, f"Failed to get logs: {response.text}"
        return response.json()
    return _get


@pytest.fixture
def get_stats(client):
    """Factory fixture to retrieve audit log statistics.

    Returns a function that gets stats and returns the response JSON.
    """
    def _get(project_id, api_key):
        response = client.get(
            f"/logs/{project_id}/stats",
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200, f"Failed to get stats: {response.text}"
        return response.json()
    return _get
