"""Error codes and message catalog for consistent API error responses."""

from enum import Enum


class ErrorCode(str, Enum):
    """Machine-readable error codes."""

    # Authentication (401)
    MISSING_API_KEY = "missing_api_key"

    # Authorization (403)
    INVALID_API_KEY = "invalid_api_key"
    PROJECT_INACTIVE = "project_inactive"
    PROJECT_MISMATCH = "project_mismatch"

    # Not Found (404)
    PROJECT_NOT_FOUND = "project_not_found"
    POLICY_NOT_FOUND = "policy_not_found"
    TEMPLATE_NOT_FOUND = "template_not_found"

    # Conflict (409)
    PROJECT_EXISTS = "project_exists"

    # Validation (422)
    INVALID_REQUEST = "invalid_request"
    INVALID_POLICY = "invalid_policy"
    INVALID_FIELD = "invalid_field"

    # Server Error (500/503/504)
    SERVICE_UNAVAILABLE = "service_unavailable"
    INTERNAL_ERROR = "internal_error"
    REQUEST_TIMEOUT = "request_timeout"


# Error message templates with hints
ERROR_MESSAGES: dict[ErrorCode, dict] = {
    # Authentication
    ErrorCode.MISSING_API_KEY: {
        "message": "API key is required",
        "hint": "Include your API key in the X-API-Key header. You receive an API key when creating a project.",
        "docs_url": "/docs#section/Authentication",
    },
    # Authorization
    ErrorCode.INVALID_API_KEY: {
        "message": "The provided API key is invalid",
        "hint": "Check that you're using the correct API key for this project. API keys start with 'af_'.",
    },
    ErrorCode.PROJECT_INACTIVE: {
        "message": "This project has been deactivated",
        "hint": "Contact your administrator to reactivate the project, or create a new project.",
    },
    ErrorCode.PROJECT_MISMATCH: {
        "message": "API key does not match the requested project",
        "hint": "Ensure the project_id in your request matches the project associated with your API key.",
    },
    # Not Found
    ErrorCode.PROJECT_NOT_FOUND: {
        "message": "Project not found",
        "hint": "Create a new project using POST /projects, or verify the project ID is correct.",
    },
    ErrorCode.POLICY_NOT_FOUND: {
        "message": "No active policy found for this project",
        "hint": "Create a policy using POST /policies/{project_id}, or apply a template using POST /templates/{template_id}/apply/{project_id}. Available templates: finance, healthcare, general.",
    },
    ErrorCode.TEMPLATE_NOT_FOUND: {
        "message": "Policy template not found",
        "hint": "Available templates: finance, healthcare, general. Use GET /templates to list all templates.",
    },
    # Conflict
    ErrorCode.PROJECT_EXISTS: {
        "message": "A project with this ID already exists",
        "hint": "Choose a different project ID, or use GET /projects/{id} to check if the existing project meets your needs.",
    },
    # Validation
    ErrorCode.INVALID_REQUEST: {
        "message": "Invalid request format",
        "hint": "Check that your request body is valid JSON and includes all required fields.",
    },
    ErrorCode.INVALID_POLICY: {
        "message": "Invalid policy configuration",
        "hint": "Check your policy rules syntax. See /docs#section/Policy-Format for the correct format.",
    },
    ErrorCode.INVALID_FIELD: {
        "message": "Invalid field value",
        "hint": "Check the field value matches the expected type and format.",
    },
    # Server
    ErrorCode.SERVICE_UNAVAILABLE: {
        "message": "Service temporarily unavailable",
        "hint": "The service is experiencing issues. Please retry your request in a few seconds.",
    },
    ErrorCode.INTERNAL_ERROR: {
        "message": "An unexpected error occurred",
        "hint": "Please retry your request. If the problem persists, contact support.",
    },
    ErrorCode.REQUEST_TIMEOUT: {
        "message": "Request timed out",
        "hint": "The server took too long to process your request. Try again or reduce the complexity of your request.",
    },
}


def make_error(code: ErrorCode, **overrides) -> dict:
    """
    Build an error response dict for the given error code.

    Args:
        code: The ErrorCode enum value
        **overrides: Optional field overrides (message, hint, docs_url, field)

    Returns:
        Dict with {"error": {...}} structure ready for HTTPException.detail

    Example:
        raise HTTPException(
            status_code=404,
            detail=make_error(ErrorCode.POLICY_NOT_FOUND, hint="Custom hint here"),
        )
    """
    base = ERROR_MESSAGES.get(code, {
        "message": "An error occurred",
        "hint": None,
    })

    error = {
        "code": code.value,
        "message": base.get("message", "An error occurred"),
    }

    # Add optional fields if present
    if base.get("hint"):
        error["hint"] = base["hint"]
    if base.get("docs_url"):
        error["docs_url"] = base["docs_url"]

    # Apply overrides
    error.update(overrides)

    return {"error": error}
