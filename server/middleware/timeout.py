"""Request timeout middleware."""

import asyncio
import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from server.errors import ErrorCode, make_error

logger = logging.getLogger(__name__)


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce request timeout with structured error response.

    Returns HTTP 504 Gateway Timeout with structured JSON error when
    a request exceeds the configured timeout.
    """

    def __init__(self, app, timeout: float = 30.0):
        """
        Initialize the timeout middleware.

        Args:
            app: The ASGI application
            timeout: Maximum request duration in seconds (default: 30.0)
        """
        super().__init__(app)
        self.timeout = timeout

    async def dispatch(self, request: Request, call_next):
        """Process request with timeout enforcement."""
        try:
            return await asyncio.wait_for(
                call_next(request),
                timeout=self.timeout
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"Request timeout after {self.timeout}s: {request.method} {request.url.path}",
                extra={
                    "timeout_seconds": self.timeout,
                    "method": request.method,
                    "path": request.url.path,
                },
            )
            return JSONResponse(
                status_code=504,
                content=make_error(ErrorCode.REQUEST_TIMEOUT),
            )
