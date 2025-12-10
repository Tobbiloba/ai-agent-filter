"""API routes package."""

from server.routes.validate import router as validate_router
from server.routes.policies import router as policies_router
from server.routes.logs import router as logs_router
from server.routes.projects import router as projects_router
from server.routes.templates import router as templates_router

__all__ = [
    "validate_router",
    "policies_router",
    "logs_router",
    "projects_router",
    "templates_router",
]
