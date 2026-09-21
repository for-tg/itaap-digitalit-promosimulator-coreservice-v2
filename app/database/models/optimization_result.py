"""Optimization result database model."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database import Base

if TYPE_CHECKING:
    from app.database.models.scenario import Scenario


def utc_now() -> datetime:
    """Return the current UTC datetime."""

    return datetime.now(timezone.utc)


class OptimizationResult(Base):
    """Stores one active optimization result for each scenario."""

    __tablename__ = "optimization_result"

    scenario_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "scenario.scenario_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    result_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
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

    scenario: Mapped["Scenario"] = relationship(
        "Scenario",
        back_populates="optimization_result",
    )