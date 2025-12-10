"""Pydantic schemas for projects."""

from datetime import datetime
from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    """Schema for creating a project."""

    id: str = Field(..., description="Unique project identifier")
    name: str = Field(..., description="Project display name")
    webhook_url: str | None = Field(None, description="Webhook URL for notifications")
    webhook_enabled: bool = Field(False, description="Enable webhook notifications")

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
    webhook_url: str | None = Field(None, description="Webhook URL for notifications")
    webhook_enabled: bool = Field(False, description="Webhook notifications enabled")
    created_at: datetime = Field(..., description="When the project was created")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "finbot-123",
                "name": "Finance Bot Production",
                "api_key": "af_aBcDeFgHiJkLmNoPqRsTuVwXyZ123456789",
                "is_active": True,
                "webhook_url": "https://hooks.slack.com/services/xxx",
                "webhook_enabled": True,
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
    webhook_url: str | None = None
    webhook_enabled: bool = False
    created_at: datetime


class ProjectUpdate(BaseModel):
    """Schema for updating a project."""

    name: str | None = Field(None, description="Project display name")
    webhook_url: str | None = Field(None, description="Webhook URL for notifications")
    webhook_enabled: bool | None = Field(None, description="Enable webhook notifications")
