"""Scenario database model."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database import Base

if TYPE_CHECKING:
    from app.database.models.optimization_result import OptimizationResult
    from app.database.models.project import Project
    from app.database.models.scenario_config import ScenarioConfig


def utc_now() -> datetime:
    """Return the current UTC datetime."""

    return datetime.now(timezone.utc)


class ScenarioStatus(str, Enum):
    """Supported scenario statuses."""

    DRAFT = "DRAFT"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Scenario(Base):
    """Scenario table."""

    __tablename__ = "scenario"

    scenario_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "project.project_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    scenario_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ScenarioStatus.DRAFT.value,
        index=True,
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

    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="scenarios",
    )

    config: Mapped["ScenarioConfig | None"] = relationship(
        "ScenarioConfig",
        back_populates="scenario",
        uselist=False,
        cascade="all, delete-orphan",
    )

    optimization_result: Mapped[
        "OptimizationResult | None"
    ] = relationship(
        "OptimizationResult",
        back_populates="scenario",
        uselist=False,
        cascade="all, delete-orphan",
    )