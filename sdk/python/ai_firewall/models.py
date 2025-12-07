"""Data models for the AI Firewall SDK."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class ValidationResult:
    """Result of an action validation."""

    allowed: bool
    action_id: str
    timestamp: datetime
    reason: str | None = None
    execution_time_ms: int | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "ValidationResult":
        """Create from API response dictionary."""
        return cls(
            allowed=data["allowed"],
            action_id=data["action_id"],
            timestamp=datetime.fromisoformat(data["timestamp"].rstrip("Z")),
            reason=data.get("reason"),
            execution_time_ms=data.get("execution_time_ms"),
        )


@dataclass
class Policy:
    """A project policy."""

    id: int
    project_id: str
    name: str
    version: str
    rules: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dict(cls, data: dict) -> "Policy":
        """Create from API response dictionary."""
        return cls(
            id=data["id"],
            project_id=data["project_id"],
            name=data["name"],
            version=data["version"],
            rules=data["rules"],
            is_active=data["is_active"],
            created_at=datetime.fromisoformat(data["created_at"].rstrip("Z")),
            updated_at=datetime.fromisoformat(data["updated_at"].rstrip("Z")),
        )


@dataclass
class AuditLogEntry:
    """An audit log entry."""

    action_id: str
    project_id: str
    agent_name: str
    action_type: str
    params: dict[str, Any]
    allowed: bool
    reason: str | None
    policy_version: str | None
    execution_time_ms: int | None
    timestamp: datetime

    @classmethod
    def from_dict(cls, data: dict) -> "AuditLogEntry":
        """Create from API response dictionary."""
        return cls(
            action_id=data["action_id"],
            project_id=data["project_id"],
            agent_name=data["agent_name"],
            action_type=data["action_type"],
            params=data["params"],
            allowed=data["allowed"],
            reason=data.get("reason"),
            policy_version=data.get("policy_version"),
            execution_time_ms=data.get("execution_time_ms"),
            timestamp=datetime.fromisoformat(data["timestamp"].rstrip("Z")),
        )


@dataclass
class LogsPage:
    """A page of audit logs."""

    items: list[AuditLogEntry]
    total: int
    page: int
    page_size: int
    has_more: bool

    @classmethod
    def from_dict(cls, data: dict) -> "LogsPage":
        """Create from API response dictionary."""
        return cls(
            items=[AuditLogEntry.from_dict(item) for item in data["items"]],
            total=data["total"],
            page=data["page"],
            page_size=data["page_size"],
            has_more=data["has_more"],
        )
