"""Integration tests for graceful shutdown and readiness endpoint."""

import pytest
from fastapi.testclient import TestClient

from server.app import app
from server.shutdown import reset_shutdown_state, set_shutting_down


@pytest.fixture
def client():
    """Create TestClient for each test."""
    # Ensure clean state before test
    reset_shutdown_state()
    with TestClient(app) as c:
        yield c
    # Ensure clean state after test
    reset_shutdown_state()


class TestReadinessEndpoint:
    """Test /ready endpoint behavior."""

    def test_ready_returns_200_when_healthy(self, client):
        """/ready should return 200 when server is ready."""
        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

    def test_ready_returns_503_during_shutdown(self, client):
        """/ready should return 503 when server is shutting down."""
        set_shutting_down()
        response = client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "shutting_down"

    def test_ready_content_type_is_json(self, client):
        """/ready should return JSON content type."""
        response = client.get("/ready")
        assert "application/json" in response.headers["content-type"]

    def test_ready_503_content_type_is_json(self, client):
        """/ready 503 response should also be JSON."""
        set_shutting_down()
        response = client.get("/ready")
        assert "application/json" in response.headers["content-type"]


class TestHealthVsReady:
    """Test the difference between /health and /ready endpoints."""

    def test_health_returns_200_when_healthy(self, client):
        """/health should return 200 when server is running."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_returns_200_during_shutdown(self, client):
        """/health should still return 200 during shutdown (liveness probe)."""
        set_shutting_down()
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_ready_returns_503_while_health_returns_200(self, client):
        """During shutdown: /ready=503, /health=200."""
        set_shutting_down()

        ready_response = client.get("/ready")
        health_response = client.get("/health")

        assert ready_response.status_code == 503
        assert health_response.status_code == 200


class TestReadinessEndpointWithCorrelationId:
    """Test /ready endpoint includes correlation ID."""

    def test_ready_includes_correlation_id(self, client):
        """/ready should include X-Correlation-ID header."""
        response = client.get("/ready")
        assert "X-Correlation-ID" in response.headers

    def test_ready_503_includes_correlation_id(self, client):
        """/ready 503 should also include X-Correlation-ID header."""
        set_shutting_down()
        response = client.get("/ready")
        assert "X-Correlation-ID" in response.headers

    def test_custom_correlation_id_echoed(self, client):
        """Custom X-Correlation-ID should be echoed back."""
        custom_id = "shutdown-test-123"
        response = client.get(
            "/ready",
            headers={"X-Correlation-ID": custom_id}
        )
        assert response.headers["X-Correlation-ID"] == custom_id
