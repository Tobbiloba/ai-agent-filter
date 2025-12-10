"""Main FastAPI application."""

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from server.config import get_settings
from server.database import init_db, close_db, get_database_type
from server.cache import init_cache, close_cache, get_cache
from server.logging_config import setup_logging
from server.middleware.correlation import CorrelationIdMiddleware
from server.routes import validate_router, policies_router, logs_router, projects_router, templates_router
from server.metrics import (
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_IN_PROGRESS,
    normalize_endpoint,
)
from server.shutdown import is_shutting_down, set_shutting_down

settings = get_settings()
logger = logging.getLogger(__name__)


def get_in_flight_count() -> int:
    """Get total number of in-flight requests from Prometheus metric."""
    total = 0
    for metric in HTTP_REQUESTS_IN_PROGRESS.collect():
        for sample in metric.samples:
            if sample.name == "http_requests_in_progress":
                total += int(sample.value)
    return total


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect HTTP request metrics for Prometheus."""

    async def dispatch(self, request: Request, call_next):
        """Process request and record metrics."""
        method = request.method
        # Normalize endpoint to avoid high cardinality
        endpoint = normalize_endpoint(request.url.path)

        # Skip metrics for the /metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)

        HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).inc()
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_code = 500
            raise
        finally:
            duration = time.perf_counter() - start_time
            HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).dec()
            HTTP_REQUESTS_TOTAL.labels(
                method=method, endpoint=endpoint, status_code=status_code
            ).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=method, endpoint=endpoint
            ).observe(duration)

            # Log completed request with structured data
            logger.info(
                "request_completed",
                extra={
                    "method": method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": round(duration * 1000, 2),
                },
            )

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup - configure logging first
    setup_logging(settings.log_level, settings.log_json)
    logger.info("Starting AI Agent Safety Filter", extra={"version": "0.1.0"})

    await init_db()
    await init_cache()
    yield

    # Shutdown - graceful drain
    set_shutting_down()

    # Wait for in-flight requests to complete
    timeout = settings.shutdown_timeout
    start = asyncio.get_event_loop().time()

    while get_in_flight_count() > 0:
        elapsed = asyncio.get_event_loop().time() - start
        if elapsed >= timeout:
            remaining = get_in_flight_count()
            logger.warning(
                f"Shutdown timeout reached with {remaining} requests still in-flight"
            )
            break
        await asyncio.sleep(0.1)

    logger.info("All requests drained, closing connections")
    await close_cache()
    await close_db()


app = FastAPI(
    title="AI Agent Safety Filter",
    description="Middleware that intercepts AI agent actions, validates them against policy rules, and logs all activity.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Correlation ID middleware (must be outermost to capture all requests)
app.add_middleware(CorrelationIdMiddleware)

# Metrics middleware (must be added after CORS)
app.add_middleware(MetricsMiddleware)


@app.get("/health")
async def health_check():
    """Health check endpoint (liveness probe).

    Always returns 200 if the server is running, even during shutdown.
    Use /ready for readiness checks.
    """
    cache = get_cache()
    return {
        "status": "healthy",
        "version": "0.1.0",
        "database": get_database_type(),
        "cache": "redis" if cache.is_available else "disabled",
    }


@app.get("/ready")
async def readiness_check():
    """Readiness probe for Kubernetes.

    Returns 503 during shutdown to stop receiving new traffic.
    Use this endpoint for load balancer health checks.
    """
    if is_shutting_down():
        return Response(
            content='{"status": "shutting_down"}',
            status_code=503,
            media_type="application/json",
        )
    return {"status": "ready"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint.

    Returns metrics in Prometheus text format for scraping.
    Includes:
    - http_requests_total: Request count by method, endpoint, status
    - http_request_duration_seconds: Request latency histogram
    - http_requests_in_progress: Current in-flight requests
    - validation_total: Validation requests by project, outcome
    - validation_duration_seconds: Validation latency histogram
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "AI Agent Safety Filter",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


# Include routers
app.include_router(validate_router)
app.include_router(policies_router)
app.include_router(templates_router)
app.include_router(logs_router)
app.include_router(projects_router)
