"""Pydantic schemas for projects."""

from datetime import datetime
from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    """Schema for creating a project."""

    id: str = Field(..., description="Unique project identifier")
    name: str = Field(..., description="Project display name")

    model_config = {
        "json_schema_extra": {
            "example": {"id": "finbot-123", "name": "Finance Bot Production"}
        }
    }


class ProjectResponse(BaseModel):
    """Response schema for a project."""

    id: str = Field(..., description="Project identifier")
    name: str = Field(..., description="Project name")
    api_key: str = Field(..., description="API key for authentication")
    is_active: bool = Field(..., description="Whether the project is active")
    created_at: datetime = Field(..., description="When the project was created")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "finbot-123",
                "name": "Finance Bot Production",
                "api_key": "af_aBcDeFgHiJkLmNoPqRsTuVwXyZ123456789",
                "is_active": True,
                "created_at": "2025-12-07T10:00:00Z",
            }
        }
    }


class ProjectPublic(BaseModel):
    """Public response schema (without full API key)."""

    id: str
    name: str
    api_key_preview: str = Field(..., description="First 10 chars of API key")
    is_active: bool
    created_at: datetime
