"""Pydantic schemas for policies."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class PolicyRule(BaseModel):
    """A single policy rule."""

    action_type: str = Field(
        default="*", description="Action type this rule applies to (* for all)"
    )
    constraints: dict[str, dict[str, Any]] | None = Field(
        None, description="Parameter constraints"
    )
    allowed_agents: list[str] | None = Field(
        None, description="Whitelist of allowed agents"
    )
    blocked_agents: list[str] | None = Field(
        None, description="Blacklist of blocked agents"
    )
    rate_limit: dict[str, int] | None = Field(
        None, description="Rate limit configuration"
    )
    aggregate_limit: dict[str, Any] | None = Field(
        None, description="Aggregate limit configuration for cumulative tracking"
    )


class PolicyCreate(BaseModel):
    """Schema for creating/updating a policy."""

    name: str = Field(default="default", description="Policy name")
    version: str = Field(default="1.0", description="Policy version")
    default: str = Field(
        default="allow", description="Default behavior (allow or block)"
    )
    rules: list[PolicyRule] = Field(
        default_factory=list, description="List of policy rules"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "invoice-policy",
                "version": "1.0",
                "default": "allow",
                "rules": [
                    {
                        "action_type": "pay_invoice",
                        "constraints": {
                            "params.amount": {"max": 10000, "min": 0},
                            "params.currency": {"in": ["USD", "EUR"]},
                        },
                        "aggregate_limit": {
                            "max_value": 50000,
                            "window": "daily",
                            "param_path": "amount",
                            "measure": "sum",
                            "scope": "agent",
                        },
                    },
                    {
                        "action_type": "*",
                        "rate_limit": {"max_requests": 100, "window_seconds": 3600},
                    },
                ],
            }
        }
    }


class PolicyResponse(BaseModel):
    """Response schema for a policy."""

    id: int = Field(..., description="Policy ID")
    project_id: str = Field(..., description="Project this policy belongs to")
    name: str = Field(..., description="Policy name")
    version: str = Field(..., description="Policy version")
    rules: dict[str, Any] = Field(..., description="Policy rules as JSON")
    is_active: bool = Field(..., description="Whether this policy is active")
    created_at: datetime = Field(..., description="When the policy was created")
    updated_at: datetime = Field(..., description="When the policy was last updated")
