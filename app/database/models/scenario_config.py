"""Scenario configuration database model."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.config.database import Base


def utc_now() -> datetime:
    """Return the current UTC datetime."""

    return datetime.now(timezone.utc)


class ScenarioConfig(Base):
    """Stores one active configuration for each scenario."""

    __tablename__ = "scenario_config"

    scenario_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "scenario.scenario_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    analysis_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="retro",
    )

    objective: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="profit",
    )

    economics: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="tn",
    )

    selected_skus: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    year: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    plan_year: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    base_year: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    reference_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=2025,
    )

    period: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="Full year",
    )

    use_trend: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    max_discount: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.25,
    )

    budget_multiplier: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
    )

    unconstrained: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    alpha: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    margin_floor: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    allocation_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="actual",
    )

    quarterly_splits: Mapped[dict[str, float]] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: {
            "Q1": 25.0,
            "Q2": 25.0,
            "Q3": 25.0,
            "Q4": 25.0,
        },
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

    scenario = relationship(
        "Scenario",
        back_populates="config",
    )