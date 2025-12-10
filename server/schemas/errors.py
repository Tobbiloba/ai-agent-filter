"""Pydantic schemas for error responses."""

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Detailed error information with actionable guidance."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    hint: str | None = Field(None, description="Actionable guidance to fix the error")
    docs_url: str | None = Field(None, description="Link to relevant documentation")
    field: str | None = Field(None, description="Field name for validation errors")

    model_config = {
        "json_schema_extra": {
            "example": {
                "code": "missing_api_key",
                "message": "API key is required",
                "hint": "Include your API key in the X-API-Key header.",
                "docs_url": "/docs#authentication",
            }
        }
    }


class ErrorResponse(BaseModel):
    """Standard error response wrapper."""

    error: ErrorDetail

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": {
                    "code": "missing_api_key",
                    "message": "API key is required",
                    "hint": "Include your API key in the X-API-Key header.",
                }
            }
        }
    }


class ValidationErrorDetail(BaseModel):
    """Validation error for a specific field."""

    code: str = Field(default="invalid_field", description="Error code")
    message: str = Field(..., description="Error message")
    field: str = Field(..., description="Field path that caused the error")
    hint: str | None = Field(None, description="How to fix the error")


class ValidationErrorResponse(BaseModel):
    """Response for validation errors (422)."""

    errors: list[ValidationErrorDetail]

    model_config = {
        "json_schema_extra": {
            "example": {
                "errors": [
                    {
                        "code": "invalid_field",
                        "message": "Field required",
                        "field": "body.project_id",
                        "hint": "Check the 'project_id' field in your request.",
                    }
                ]
            }
        }
    }
