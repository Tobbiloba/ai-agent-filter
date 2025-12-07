"""Policy model - stores validation rules for a project."""

from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.database import Base


class Policy(Base):
    """Policy model - contains rules for validating agent actions."""

    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="default")
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")
    rules: Mapped[str] = mapped_column(Text, nullable=False)  # JSON stored as text
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="policies")

    def __repr__(self) -> str:
        return f"<Policy {self.id}: {self.name} v{self.version}>"
