"""Integration tests for aggregate limits.

These tests verify end-to-end aggregate limit functionality using
the actual database and validation pipeline.
"""

import pytest
import json
import time
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
    return f"agg-{int(time.time() * 1000)}"


@pytest.fixture
def create_project(client, unique_id):
    """Create a test project."""
    response = client.post("/projects", json={
        "id": unique_id,
        "name": "Aggregate Test Project"
    })
    assert response.status_code == 200, f"Failed to create project: {response.text}"
    data = response.json()
    return unique_id, data["api_key"]


class TestAggregateLimitsDailySum:
    """Test daily sum aggregate limits."""

    def test_allows_actions_under_daily_limit(self, client, create_project):
        """Actions under the daily limit should be allowed."""
        project_id, api_key = create_project

        # Create policy with aggregate limit
        response = client.post(
            f"/policies/{project_id}",
            json={
                "name": "daily-limit",
                "version": "1.0",
                "default": "allow",
                "rules": [{
                    "action_type": "pay_invoice",
                    "aggregate_limit": {
                        "max_value": 1000,
                        "window": "daily",
                        "param_path": "amount",
                        "measure": "sum",
                        "scope": "agent"
                    }
                }]
            },
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200

        # Action under limit should be allowed
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "invoice_agent",
                "action_type": "pay_invoice",
                "params": {"amount": 500}
            },
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        assert response.json()["allowed"] is True

    def test_blocks_when_daily_limit_exceeded(self, client, create_project):
        """Actions exceeding daily limit should be blocked."""
        project_id, api_key = create_project

        # Create policy with aggregate limit
        client.post(
            f"/policies/{project_id}",
            json={
                "name": "daily-limit",
                "version": "1.0",
                "default": "allow",
                "rules": [{
                    "action_type": "pay_invoice",
                    "aggregate_limit": {
                        "max_value": 1000,
                        "window": "daily",
                        "param_path": "amount",
                        "measure": "sum",
                        "scope": "agent"
                    }
                }]
            },
            headers={"X-API-Key": api_key}
        )

        # First request: 600 (allowed)
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "invoice_agent",
                "action_type": "pay_invoice",
                "params": {"amount": 600}
            },
            headers={"X-API-Key": api_key}
        )
        assert response.json()["allowed"] is True

        # Second request: 500 (600 + 500 = 1100 > 1000, blocked)
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "invoice_agent",
                "action_type": "pay_invoice",
                "params": {"amount": 500}
            },
            headers={"X-API-Key": api_key}
        )
        assert response.json()["allowed"] is False
        assert "Aggregate limit exceeded" in response.json()["reason"]

    def test_allows_exactly_at_limit(self, client, create_project):
        """Action that exactly reaches the limit should be allowed."""
        project_id, api_key = create_project

        # Create policy
        client.post(
            f"/policies/{project_id}",
            json={
                "name": "daily-limit",
                "version": "1.0",
                "default": "allow",
                "rules": [{
                    "action_type": "pay_invoice",
                    "aggregate_limit": {
                        "max_value": 1000,
                        "window": "daily",
                        "param_path": "amount",
                        "measure": "sum",
                        "scope": "agent"
                    }
                }]
            },
            headers={"X-API-Key": api_key}
        )

        # Exactly 1000 should be allowed
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "invoice_agent",
                "action_type": "pay_invoice",
                "params": {"amount": 1000}
            },
            headers={"X-API-Key": api_key}
        )
        assert response.json()["allowed"] is True

        # Any additional amount should be blocked
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "invoice_agent",
                "action_type": "pay_invoice",
                "params": {"amount": 1}
            },
            headers={"X-API-Key": api_key}
        )
        assert response.json()["allowed"] is False


class TestAggregateLimitsCountMeasure:
    """Test count-based aggregate limits."""

    def test_allows_actions_up_to_count_limit(self, client, create_project):
        """Should allow exactly count limit actions."""
        project_id, api_key = create_project

        # Create policy with count limit
        client.post(
            f"/policies/{project_id}",
            json={
                "name": "count-limit",
                "version": "1.0",
                "default": "allow",
                "rules": [{
                    "action_type": "send_email",
                    "aggregate_limit": {
                        "max_value": 3,
                        "window": "hourly",
                        "measure": "count",
                        "scope": "agent"
                    }
                }]
            },
            headers={"X-API-Key": api_key}
        )

        # First 3 should be allowed
        for i in range(3):
            response = client.post(
                "/validate_action",
                json={
                    "project_id": project_id,
                    "agent_name": "email_agent",
                    "action_type": "send_email",
                    "params": {"to": f"user{i}@example.com"}
                },
                headers={"X-API-Key": api_key}
            )
            assert response.json()["allowed"] is True, f"Action {i+1} should be allowed"

        # 4th should be blocked
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "email_agent",
                "action_type": "send_email",
                "params": {"to": "user3@example.com"}
            },
            headers={"X-API-Key": api_key}
        )
        assert response.json()["allowed"] is False


class TestAggregateLimitsScope:
    """Test different aggregate limit scopes."""

    def test_agent_scope_tracks_separately(self, client, create_project):
        """Different agents should have separate limits with agent scope."""
        project_id, api_key = create_project

        # Create policy with agent scope
        client.post(
            f"/policies/{project_id}",
            json={
                "name": "agent-scope",
                "version": "1.0",
                "default": "allow",
                "rules": [{
                    "action_type": "transfer",
                    "aggregate_limit": {
                        "max_value": 500,
                        "window": "daily",
                        "param_path": "amount",
                        "measure": "sum",
                        "scope": "agent"
                    }
                }]
            },
            headers={"X-API-Key": api_key}
        )

        # Agent 1: 400 (allowed)
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "agent_one",
                "action_type": "transfer",
                "params": {"amount": 400}
            },
            headers={"X-API-Key": api_key}
        )
        assert response.json()["allowed"] is True

        # Agent 2: 400 (allowed - separate counter)
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "agent_two",
                "action_type": "transfer",
                "params": {"amount": 400}
            },
            headers={"X-API-Key": api_key}
        )
        assert response.json()["allowed"] is True

        # Agent 1: 200 (blocked - 400 + 200 = 600 > 500)
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "agent_one",
                "action_type": "transfer",
                "params": {"amount": 200}
            },
            headers={"X-API-Key": api_key}
        )
        assert response.json()["allowed"] is False


class TestAggregateLimitsWithConstraints:
    """Test aggregate limits combined with other rule types."""

    def test_constraints_checked_before_aggregate(self, client, create_project):
        """Constraints should be checked before aggregate limits."""
        project_id, api_key = create_project

        # Create policy with both constraints and aggregate limit
        client.post(
            f"/policies/{project_id}",
            json={
                "name": "combined-policy",
                "version": "1.0",
                "default": "allow",
                "rules": [{
                    "action_type": "pay_invoice",
                    "constraints": {
                        "params.amount": {"max": 5000, "min": 0},
                        "params.currency": {"in": ["USD", "EUR"]}
                    },
                    "aggregate_limit": {
                        "max_value": 10000,
                        "window": "daily",
                        "param_path": "amount",
                        "measure": "sum",
                        "scope": "agent"
                    }
                }]
            },
            headers={"X-API-Key": api_key}
        )

        # Invalid currency - blocked by constraint, not aggregate
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "invoice_agent",
                "action_type": "pay_invoice",
                "params": {"amount": 100, "currency": "GBP"}
            },
            headers={"X-API-Key": api_key}
        )
        assert response.json()["allowed"] is False
        assert "not in allowed values" in response.json()["reason"]

        # Amount too high - blocked by constraint
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "invoice_agent",
                "action_type": "pay_invoice",
                "params": {"amount": 6000, "currency": "USD"}
            },
            headers={"X-API-Key": api_key}
        )
        assert response.json()["allowed"] is False
        assert "exceeds maximum" in response.json()["reason"]


class TestAggregateLimitsNestedParams:
    """Test aggregate limits with nested parameter paths."""

    def test_extracts_nested_param_value(self, client, create_project):
        """Should extract value from nested param path."""
        project_id, api_key = create_project

        # Create policy with nested path
        client.post(
            f"/policies/{project_id}",
            json={
                "name": "nested-path",
                "version": "1.0",
                "default": "allow",
                "rules": [{
                    "action_type": "process_order",
                    "aggregate_limit": {
                        "max_value": 5000,
                        "window": "daily",
                        "param_path": "order.total.amount",
                        "measure": "sum",
                        "scope": "agent"
                    }
                }]
            },
            headers={"X-API-Key": api_key}
        )

        # First order: 3000 (allowed)
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "order_agent",
                "action_type": "process_order",
                "params": {
                    "order": {
                        "id": "ORD-123",
                        "total": {"amount": 3000, "currency": "USD"}
                    }
                }
            },
            headers={"X-API-Key": api_key}
        )
        assert response.json()["allowed"] is True

        # Second order: 3000 (blocked - 3000 + 3000 = 6000 > 5000)
        response = client.post(
            "/validate_action",
            json={
                "project_id": project_id,
                "agent_name": "order_agent",
                "action_type": "process_order",
                "params": {
                    "order": {
                        "id": "ORD-124",
                        "total": {"amount": 3000, "currency": "USD"}
                    }
                }
            },
            headers={"X-API-Key": api_key}
        )
        assert response.json()["allowed"] is False


class TestAggregateLimitsNoConfig:
    """Test behavior when no aggregate limits are configured."""

    def test_allows_unlimited_actions(self, client, create_project):
        """Should allow unlimited actions when no aggregate limit."""
        project_id, api_key = create_project

        # Create policy without aggregate limits
        client.post(
            f"/policies/{project_id}",
            json={
                "name": "no-aggregate",
                "version": "1.0",
                "default": "allow",
                "rules": [{"action_type": "simple_action"}]
            },
            headers={"X-API-Key": api_key}
        )

        # All actions should be allowed
        for i in range(10):
            response = client.post(
                "/validate_action",
                json={
                    "project_id": project_id,
                    "agent_name": "agent",
                    "action_type": "simple_action",
                    "params": {"iteration": i}
                },
                headers={"X-API-Key": api_key}
            )
            assert response.json()["allowed"] is True
