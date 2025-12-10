"""Prometheus metrics for the AI Agent Safety Filter."""

from prometheus_client import Counter, Histogram, Gauge

# HTTP-level metrics (tracked via middleware)
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "HTTP requests currently being processed",
    ["method", "endpoint"],
)

# Validation-specific metrics
VALIDATION_TOTAL = Counter(
    "validation_total",
    "Total validation requests",
    ["project_id", "allowed"],
)

VALIDATION_DURATION_SECONDS = Histogram(
    "validation_duration_seconds",
    "Validation latency in seconds",
    ["allowed"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)


def normalize_endpoint(path: str) -> str:
    """Normalize endpoint paths to avoid high cardinality from path parameters.

    Examples:
        /policies/my-project -> /policies/{project_id}
        /logs/my-project/stats -> /logs/{project_id}/stats
    """
    parts = path.strip("/").split("/")

    # Known routes with path parameters
    if len(parts) >= 2:
        if parts[0] == "policies":
            parts[1] = "{project_id}"
        elif parts[0] == "logs":
            parts[1] = "{project_id}"
        elif parts[0] == "projects" and len(parts) > 1:
            parts[1] = "{project_id}"

    return "/" + "/".join(parts) if parts[0] else "/"


def record_validation_metrics(project_id: str, allowed: bool, duration_ms: float) -> None:
    """Record validation-specific metrics.

    Args:
        project_id: The project ID for the validation
        allowed: Whether the action was allowed
        duration_ms: Validation duration in milliseconds
    """
    allowed_str = str(allowed).lower()

    VALIDATION_TOTAL.labels(
        project_id=project_id,
        allowed=allowed_str,
    ).inc()

    VALIDATION_DURATION_SECONDS.labels(
        allowed=allowed_str,
    ).observe(duration_ms / 1000.0)  # Convert ms to seconds
