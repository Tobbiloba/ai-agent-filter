"""AuditLog model - records all action validation attempts."""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Text, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.database import Base


def generate_action_id() -> str:
    """Generate a unique action ID."""
    return f"act_{uuid.uuid4().hex[:16]}"


class AuditLog(Base):
    """AuditLog model - immutable record of every action validation."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action_id: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, default=generate_action_id
    )
    project_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    agent_name: Mapped[str] = mapped_column(String(255), nullable=False)
    action_type: Mapped[str] = mapped_column(String(255), nullable=False)
    params: Mapped[str] = mapped_column(Text, nullable=False)  # JSON stored as text
    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="audit_logs")

    def __repr__(self) -> str:
        status = "allowed" if self.allowed else "blocked"
        return f"<AuditLog {self.action_id}: {self.action_type} ({status})>"
