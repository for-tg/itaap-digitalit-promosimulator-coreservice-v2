"""Project database model."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.config.database import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship

def utc_now() -> datetime:
    """Return the current UTC datetime."""

    return datetime.now(timezone.utc)


class Project(Base):
    """Project table."""

    __tablename__ = "project"

    scenarios = relationship(
    "Scenario",
    back_populates="project",
    cascade="all, delete-orphan",
    )

    project_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    project_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    markets: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    mags: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    retailers: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert the project model into a response dictionary."""

        return {
            "project_id": self.project_id,
            "user_id": self.user_id,
            "project_name": self.project_name,
            "markets": self.markets or [],
            "mags": self.mags or [],
            "retailers": self.retailers or [],
            "description": self.description,
            "is_deleted": self.is_deleted,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }