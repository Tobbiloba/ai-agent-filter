"""Integration tests for Prometheus /metrics endpoint."""

import pytest
import time
from fastapi.testclient import TestClient

from server.app import app


@pytest.fixture
def client():
    """Create TestClient for each test."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def unique_id():
    """Generate unique timestamp-based ID for test isolation."""
    return f"metrics-{int(time.time() * 1000)}"


@pytest.fixture
def create_project(client, unique_id):
    """Create a test project."""
    response = client.post("/projects", json={
        "id": unique_id,
        "name": "Metrics Test Project"
    })
    assert response.status_code == 200, f"Failed to create project: {response.text}"
    data = response.json()
    return unique_id, data["api_key"]


class TestMetricsEndpoint:
    """Test the /metrics endpoint."""

    def test_metrics_endpoint_returns_200(self, client):
        """GET /metrics should return 200."""
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_endpoint_content_type(self, client):
        """Metrics endpoint should return Prometheus content type."""
        response = client.get("/metrics")
        assert "text/plain" in response.headers["content-type"]

    def test_metrics_endpoint_returns_prometheus_format(self, client):
        """Metrics should be in valid Prometheus format."""
        response = client.get("/metrics")
        content = response.text

        # Should contain HELP and TYPE comments
        assert "# HELP" in content
        assert "# TYPE" in content

    def test_metrics_contains_http_requests_total(self, client):
        """Metrics should contain http_requests_total."""
        # Make a request first to generate metrics
        client.get("/health")

        response = client.get("/metrics")
        content = response.text

        assert "http_requests_total" in content

    def test_metrics_contains_http_request_duration(self, client):
        """Metrics should contain http_request_duration_seconds."""
        client.get("/health")

        response = client.get("/metrics")
        content = response.text

        assert "http_request_duration_seconds" in content

    def test_metrics_contains_validation_total(self, client, create_project):
        """Metrics should contain validation_total after validation."""
        project_id, api_key = create_project

        # Create a policy
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

        # Do a validation
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

        response = client.get("/metrics")
        content = response.text

        assert "validation_total" in content

    def test_metrics_contains_validation_duration(self, client, create_project):
        """Metrics should contain validation_duration_seconds after validation."""
        project_id, api_key = create_project

        # Create a policy
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

        # Do a validation
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

        response = client.get("/metrics")
        content = response.text

        assert "validation_duration_seconds" in content


class TestMetricsMiddleware:
    """Test that middleware correctly records HTTP metrics."""

    def test_health_endpoint_recorded(self, client):
        """Health endpoint requests should be recorded."""
        # Make multiple requests
        for _ in range(3):
            client.get("/health")

        response = client.get("/metrics")
        content = response.text

        # Should see /health endpoint in metrics
        assert 'endpoint="/health"' in content

    def test_different_status_codes_recorded(self, client):
        """Different status codes should be recorded separately."""
        # Make a successful request
        client.get("/health")

        # Make a request that returns 404
        client.get("/nonexistent-endpoint")

        response = client.get("/metrics")
        content = response.text

        # Should see both 200 and 404 status codes
        assert 'status_code="200"' in content
        assert 'status_code="404"' in content

    def test_endpoint_normalization_in_metrics(self, client, create_project):
        """Path parameters should be normalized in metrics."""
        project_id, api_key = create_project

        # Access policies endpoint with project_id
        client.get(
            f"/policies/{project_id}",
            headers={"X-API-Key": api_key}
        )

        response = client.get("/metrics")
        content = response.text

        # Should see normalized endpoint, not actual project_id
        assert 'endpoint="/policies/{project_id}"' in content


class TestValidationMetrics:
    """Test validation-specific metrics."""

    def test_allowed_validation_recorded(self, client, create_project):
        """Allowed validations should be recorded with allowed=true."""
        project_id, api_key = create_project

        # Create permissive policy
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

        # Do validation that will be allowed
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
        assert response.json()["allowed"] is True

        # Check metrics
        metrics_response = client.get("/metrics")
        content = metrics_response.text

        assert 'validation_total{' in content
        assert 'allowed="true"' in content

    def test_blocked_validation_recorded(self, client, create_project):
        """Blocked validations should be recorded with allowed=false."""
        project_id, api_key = create_project

        # Create restrictive policy
        client.post(
            f"/policies/{project_id}",
            json={
                "name": "test-policy",
                "version": "1.0",
                "default": "block",
                "rules": []
            },
            headers={"X-API-Key": api_key}
        )

        # Do validation that will be blocked
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
        assert response.json()["allowed"] is False

        # Check metrics
        metrics_response = client.get("/metrics")
        content = metrics_response.text

        assert 'allowed="false"' in content

    def test_project_id_in_validation_metrics(self, client, create_project):
        """Project ID should appear in validation metrics."""
        project_id, api_key = create_project

        # Create policy and do validation
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

        # Check metrics contain project_id
        metrics_response = client.get("/metrics")
        content = metrics_response.text

        assert f'project_id="{project_id}"' in content


class TestHistogramBuckets:
    """Test that histogram buckets are working correctly."""

    def test_http_duration_has_buckets(self, client):
        """HTTP duration histogram should have bucket entries."""
        client.get("/health")

        response = client.get("/metrics")
        content = response.text

        # Should see bucket entries
        assert "http_request_duration_seconds_bucket" in content
        assert "http_request_duration_seconds_count" in content
        assert "http_request_duration_seconds_sum" in content

    def test_validation_duration_has_buckets(self, client, create_project):
        """Validation duration histogram should have bucket entries."""
        project_id, api_key = create_project

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

        response = client.get("/metrics")
        content = response.text

        assert "validation_duration_seconds_bucket" in content
        assert "validation_duration_seconds_count" in content
        assert "validation_duration_seconds_sum" in content
