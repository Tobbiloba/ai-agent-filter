"""Integration tests for structured logging and correlation IDs."""

import pytest
import re
import time
from fastapi.testclient import TestClient

from server.app import app
from server.middleware.correlation import CORRELATION_ID_HEADER


@pytest.fixture
def client():
    """Create TestClient for each test."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def unique_id():
    """Generate unique timestamp-based ID for test isolation."""
    return f"log-{int(time.time() * 1000)}"


class TestCorrelationIdMiddleware:
    """Test correlation ID middleware behavior."""

    def test_response_includes_correlation_id(self, client):
        """Response should include X-Correlation-ID header."""
        response = client.get("/health")
        assert response.status_code == 200
        assert CORRELATION_ID_HEADER in response.headers
        # Should be a 16-character hex string
        correlation_id = response.headers[CORRELATION_ID_HEADER]
        assert len(correlation_id) == 16
        assert re.match(r"^[a-f0-9]+$", correlation_id)

    def test_custom_correlation_id_is_echoed(self, client):
        """Custom X-Correlation-ID from request should be echoed back."""
        custom_id = "my-custom-trace-id"
        response = client.get(
            "/health",
            headers={CORRELATION_ID_HEADER: custom_id}
        )
        assert response.status_code == 200
        assert response.headers[CORRELATION_ID_HEADER] == custom_id

    def test_correlation_id_on_post_request(self, client, unique_id):
        """POST requests should also get correlation IDs."""
        response = client.post("/projects", json={
            "id": unique_id,
            "name": "Logging Test"
        })
        assert response.status_code == 200
        assert CORRELATION_ID_HEADER in response.headers

    def test_correlation_id_on_error_response(self, client):
        """Error responses should also include correlation ID."""
        response = client.get("/nonexistent-endpoint")
        assert response.status_code == 404
        assert CORRELATION_ID_HEADER in response.headers

    def test_correlation_id_on_401_response(self, client):
        """401 responses should include correlation ID."""
        response = client.post("/validate_action", json={
            "project_id": "test",
            "agent_name": "test",
            "action_type": "test",
            "params": {}
        })
        assert response.status_code == 401
        assert CORRELATION_ID_HEADER in response.headers

    def test_different_requests_get_different_ids(self, client):
        """Each request should get a unique correlation ID."""
        response1 = client.get("/health")
        response2 = client.get("/health")
        response3 = client.get("/health")

        id1 = response1.headers[CORRELATION_ID_HEADER]
        id2 = response2.headers[CORRELATION_ID_HEADER]
        id3 = response3.headers[CORRELATION_ID_HEADER]

        # All three should be different
        assert id1 != id2
        assert id2 != id3
        assert id1 != id3

    def test_correlation_id_format_valid_hex(self, client):
        """Generated correlation ID should be valid hex."""
        response = client.get("/health")
        correlation_id = response.headers[CORRELATION_ID_HEADER]

        # Should be parseable as hex
        try:
            int(correlation_id, 16)
        except ValueError:
            pytest.fail(f"Correlation ID '{correlation_id}' is not valid hex")


class TestEndpointCorrelation:
    """Test correlation ID across different endpoint types."""

    def test_health_endpoint_has_correlation(self, client):
        """Health endpoint should have correlation ID."""
        response = client.get("/health")
        assert CORRELATION_ID_HEADER in response.headers

    def test_metrics_endpoint_has_correlation(self, client):
        """Metrics endpoint should have correlation ID."""
        response = client.get("/metrics")
        assert CORRELATION_ID_HEADER in response.headers

    def test_root_endpoint_has_correlation(self, client):
        """Root endpoint should have correlation ID."""
        response = client.get("/")
        assert CORRELATION_ID_HEADER in response.headers


class TestLoggingConfig:
    """Test logging configuration through config."""

    def test_health_endpoint_works_with_logging(self, client):
        """Health endpoint should work with logging enabled."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_api_works_with_logging(self, client, unique_id):
        """API endpoints should work with logging enabled."""
        # Create project
        response = client.post("/projects", json={
            "id": unique_id,
            "name": "API Test"
        })
        assert response.status_code == 200
        api_key = response.json()["api_key"]

        # Create policy
        response = client.post(
            f"/policies/{unique_id}",
            json={
                "name": "test-policy",
                "version": "1.0",
                "default": "allow",
                "rules": []
            },
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200

        # Validate action
        response = client.post(
            "/validate_action",
            json={
                "project_id": unique_id,
                "agent_name": "test-agent",
                "action_type": "test-action",
                "params": {}
            },
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        assert response.json()["allowed"] is True


class TestCorrelationIdPropagation:
    """Test that correlation IDs propagate through the request lifecycle."""

    def test_correlation_id_in_validation_flow(self, client, unique_id):
        """Correlation ID should be consistent through validation flow."""
        custom_id = "validation-flow-test"

        # Create project
        response = client.post(
            "/projects",
            json={"id": unique_id, "name": "Correlation Test"},
            headers={CORRELATION_ID_HEADER: custom_id}
        )
        assert response.headers[CORRELATION_ID_HEADER] == custom_id
        api_key = response.json()["api_key"]

        # Create policy with same correlation ID
        response = client.post(
            f"/policies/{unique_id}",
            json={
                "name": "test-policy",
                "version": "1.0",
                "default": "allow",
                "rules": []
            },
            headers={"X-API-Key": api_key, CORRELATION_ID_HEADER: custom_id}
        )
        assert response.headers[CORRELATION_ID_HEADER] == custom_id

        # Validate with same correlation ID
        response = client.post(
            "/validate_action",
            json={
                "project_id": unique_id,
                "agent_name": "test",
                "action_type": "test",
                "params": {}
            },
            headers={"X-API-Key": api_key, CORRELATION_ID_HEADER: custom_id}
        )
        assert response.headers[CORRELATION_ID_HEADER] == custom_id


class TestCorrelationIdEdgeCases:
    """Test edge cases for correlation ID handling."""

    def test_empty_correlation_id_generates_new(self, client):
        """Empty correlation ID header should generate a new one."""
        response = client.get(
            "/health",
            headers={CORRELATION_ID_HEADER: ""}
        )
        # Empty string is falsy, so should generate new ID
        correlation_id = response.headers[CORRELATION_ID_HEADER]
        assert len(correlation_id) == 16

    def test_long_correlation_id_preserved(self, client):
        """Long correlation ID should be preserved."""
        long_id = "a" * 100
        response = client.get(
            "/health",
            headers={CORRELATION_ID_HEADER: long_id}
        )
        assert response.headers[CORRELATION_ID_HEADER] == long_id

    def test_special_characters_in_correlation_id(self, client):
        """Correlation ID with special characters should work."""
        special_id = "trace-123_abc.def"
        response = client.get(
            "/health",
            headers={CORRELATION_ID_HEADER: special_id}
        )
        assert response.headers[CORRELATION_ID_HEADER] == special_id
