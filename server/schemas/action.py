"""Pydantic schemas for action validation."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class ActionRequest(BaseModel):
    """Request schema for validating an action."""

    project_id: str = Field(..., description="Project identifier")
    agent_name: str = Field(..., description="Name of the agent performing the action")
    action_type: str = Field(..., description="Type of action being performed")
    params: dict[str, Any] = Field(
        default_factory=dict, description="Parameters for the action"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "project_id": "finbot-123",
                "agent_name": "invoice_agent",
                "action_type": "pay_invoice",
                "params": {"vendor": "VendorA", "amount": 5000, "currency": "USD"},
            }
        }
    }


class ActionResponse(BaseModel):
    """Response schema for action validation."""

    allowed: bool = Field(..., description="Whether the action is allowed")
    action_id: str = Field(..., description="Unique identifier for this action")
    timestamp: datetime = Field(..., description="When the validation occurred")
    reason: str | None = Field(
        None, description="Reason for blocking (only present if blocked)"
    )
    execution_time_ms: int | None = Field(
        None, description="Time taken to validate in milliseconds"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "allowed": True,
                    "action_id": "act_abc123def456",
                    "timestamp": "2025-12-07T10:30:00Z",
                    "execution_time_ms": 5,
                },
                {
                    "allowed": False,
                    "action_id": "act_xyz789uvw012",
                    "timestamp": "2025-12-07T10:30:00Z",
                    "reason": "Amount 15000 exceeds maximum allowed 10000",
                    "execution_time_ms": 3,
                },
            ]
        }
    }
