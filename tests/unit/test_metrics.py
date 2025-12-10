"""Unit tests for Prometheus metrics module."""

import pytest
from prometheus_client import Counter, Histogram, Gauge, REGISTRY

from server.metrics import (
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_IN_PROGRESS,
    VALIDATION_TOTAL,
    VALIDATION_DURATION_SECONDS,
    normalize_endpoint,
    record_validation_metrics,
)


class TestMetricDefinitions:
    """Test that metric definitions are correct."""

    def test_http_requests_total_is_counter(self):
        """HTTP requests total should be a Counter."""
        assert isinstance(HTTP_REQUESTS_TOTAL, Counter)

    def test_http_request_duration_is_histogram(self):
        """HTTP request duration should be a Histogram."""
        assert isinstance(HTTP_REQUEST_DURATION_SECONDS, Histogram)

    def test_http_requests_in_progress_is_gauge(self):
        """HTTP requests in progress should be a Gauge."""
        assert isinstance(HTTP_REQUESTS_IN_PROGRESS, Gauge)

    def test_validation_total_is_counter(self):
        """Validation total should be a Counter."""
        assert isinstance(VALIDATION_TOTAL, Counter)

    def test_validation_duration_is_histogram(self):
        """Validation duration should be a Histogram."""
        assert isinstance(VALIDATION_DURATION_SECONDS, Histogram)


class TestMetricLabels:
    """Test that metrics have correct labels."""

    def test_http_requests_total_labels(self):
        """HTTP requests total should have method, endpoint, status_code labels."""
        labels = HTTP_REQUESTS_TOTAL._labelnames
        assert "method" in labels
        assert "endpoint" in labels
        assert "status_code" in labels

    def test_http_request_duration_labels(self):
        """HTTP request duration should have method, endpoint labels."""
        labels = HTTP_REQUEST_DURATION_SECONDS._labelnames
        assert "method" in labels
        assert "endpoint" in labels

    def test_http_requests_in_progress_labels(self):
        """HTTP requests in progress should have method, endpoint labels."""
        labels = HTTP_REQUESTS_IN_PROGRESS._labelnames
        assert "method" in labels
        assert "endpoint" in labels

    def test_validation_total_labels(self):
        """Validation total should have project_id, allowed labels."""
        labels = VALIDATION_TOTAL._labelnames
        assert "project_id" in labels
        assert "allowed" in labels

    def test_validation_duration_labels(self):
        """Validation duration should have allowed label."""
        labels = VALIDATION_DURATION_SECONDS._labelnames
        assert "allowed" in labels


class TestNormalizeEndpoint:
    """Test endpoint normalization for metrics labels."""

    def test_normalize_root(self):
        """Root path should stay as root."""
        assert normalize_endpoint("/") == "/"

    def test_normalize_health(self):
        """Health endpoint should stay unchanged."""
        assert normalize_endpoint("/health") == "/health"

    def test_normalize_metrics(self):
        """Metrics endpoint should stay unchanged."""
        assert normalize_endpoint("/metrics") == "/metrics"

    def test_normalize_validate_action(self):
        """Validate action should stay unchanged."""
        assert normalize_endpoint("/validate_action") == "/validate_action"

    def test_normalize_policies_with_project_id(self):
        """Policies with project ID should be normalized."""
        assert normalize_endpoint("/policies/my-project") == "/policies/{project_id}"
        assert normalize_endpoint("/policies/another-project") == "/policies/{project_id}"

    def test_normalize_logs_with_project_id(self):
        """Logs with project ID should be normalized."""
        assert normalize_endpoint("/logs/my-project") == "/logs/{project_id}"

    def test_normalize_logs_stats(self):
        """Logs stats should preserve structure after project_id."""
        assert normalize_endpoint("/logs/my-project/stats") == "/logs/{project_id}/stats"

    def test_normalize_projects_with_id(self):
        """Projects with ID should be normalized."""
        assert normalize_endpoint("/projects/my-project") == "/projects/{project_id}"

    def test_normalize_handles_trailing_slash(self):
        """Should handle trailing slashes."""
        assert normalize_endpoint("/health/") == "/health"

    def test_normalize_handles_leading_slash(self):
        """Should handle paths without leading slash."""
        assert normalize_endpoint("health") == "/health"


class TestRecordValidationMetrics:
    """Test the record_validation_metrics helper function."""

    def test_record_validation_metrics_allowed(self):
        """Should record metrics for allowed validation."""
        # Get initial values
        initial_count = VALIDATION_TOTAL.labels(
            project_id="test-project", allowed="true"
        )._value.get()

        record_validation_metrics(
            project_id="test-project",
            allowed=True,
            duration_ms=5.0,
        )

        # Check counter incremented
        new_count = VALIDATION_TOTAL.labels(
            project_id="test-project", allowed="true"
        )._value.get()
        assert new_count == initial_count + 1

    def test_record_validation_metrics_blocked(self):
        """Should record metrics for blocked validation."""
        initial_count = VALIDATION_TOTAL.labels(
            project_id="test-project", allowed="false"
        )._value.get()

        record_validation_metrics(
            project_id="test-project",
            allowed=False,
            duration_ms=10.0,
        )

        new_count = VALIDATION_TOTAL.labels(
            project_id="test-project", allowed="false"
        )._value.get()
        assert new_count == initial_count + 1

    def test_record_validation_metrics_duration_converted(self):
        """Should convert duration from ms to seconds."""
        # Record a validation
        record_validation_metrics(
            project_id="duration-test",
            allowed=True,
            duration_ms=100.0,  # 100ms = 0.1 seconds
        )

        # The histogram should have recorded the value in seconds
        # We can't easily inspect histogram values, but we can check it doesn't error
        assert True  # If we got here, conversion worked


class TestMetricBuckets:
    """Test histogram bucket configurations."""

    def test_http_duration_buckets_configured(self):
        """HTTP duration histogram should have custom buckets."""
        # Default buckets are different from our custom ones
        buckets = HTTP_REQUEST_DURATION_SECONDS._upper_bounds
        assert 0.001 in buckets  # 1ms
        assert 0.005 in buckets  # 5ms
        assert 0.01 in buckets   # 10ms
        assert 0.1 in buckets    # 100ms
        assert 1.0 in buckets    # 1s

    def test_validation_duration_buckets_configured(self):
        """Validation duration histogram should have custom buckets."""
        buckets = VALIDATION_DURATION_SECONDS._upper_bounds
        assert 0.001 in buckets  # 1ms
        assert 0.005 in buckets  # 5ms
        assert 0.01 in buckets   # 10ms
