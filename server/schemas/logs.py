"""Pydantic schemas for audit logs."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class AuditLogResponse(BaseModel):
    """Response schema for an audit log entry."""

    action_id: str = Field(..., description="Unique action identifier")
    project_id: str = Field(..., description="Project identifier")
    agent_name: str = Field(..., description="Agent that performed the action")
    action_type: str = Field(..., description="Type of action")
    params: dict[str, Any] = Field(..., description="Action parameters")
    allowed: bool = Field(..., description="Whether action was allowed")
    reason: str | None = Field(None, description="Reason for blocking")
    policy_version: str | None = Field(None, description="Policy version used")
    execution_time_ms: int | None = Field(None, description="Validation time in ms")
    timestamp: datetime = Field(..., description="When the action occurred")


class AuditLogList(BaseModel):
    """Paginated list of audit logs."""

    items: list[AuditLogResponse] = Field(..., description="List of log entries")
    total: int = Field(..., description="Total number of entries")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    has_more: bool = Field(..., description="Whether there are more pages")
