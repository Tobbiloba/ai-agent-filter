"""Correlation ID middleware for request tracing."""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from server.logging_config import correlation_id

# Header name for correlation ID (industry standard)
CORRELATION_ID_HEADER = "X-Correlation-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that extracts or generates a correlation ID for each request.

    The correlation ID is used to trace requests across the system and appears
    in all log entries for the duration of the request.

    - If the incoming request has an X-Correlation-ID header, it is used
    - Otherwise, a new unique ID is generated
    - The correlation ID is echoed back in the response header
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and manage correlation ID."""
        # Use existing header or generate new ID
        req_id = request.headers.get(CORRELATION_ID_HEADER) or uuid.uuid4().hex[:16]

        # Set context variable for this request
        token = correlation_id.set(req_id)

        try:
            response = await call_next(request)
            # Echo correlation ID in response header
            response.headers[CORRELATION_ID_HEADER] = req_id
            return response
        finally:
            # Reset context variable
            correlation_id.reset(token)
