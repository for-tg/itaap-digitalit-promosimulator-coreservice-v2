"""Pydantic request models for the Promo Simulator API."""

from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field


class RetroRequest(BaseModel):
    """Request model for retrospective simulation."""

    economics: Literal["tn", "legacy"] = "tn"

    skus: List[str] = Field(
        ...,
        min_length=1,
        description="List of SKUs to simulate.",
    )
    # Left unset so the router can fall back to the loaded market's last
    # history year instead of a Czech-era literal.
    year: Optional[int] = Field(default=None, ge=2000)
    period: str = "Full year"
    objective: str = "profit"
    max_discount: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    budget_multiplier: float = Field(
        default=1.0,
        gt=0.0,
    )
    ref_year: Optional[int] = Field(
        default=None,
        ge=2000,
    )
    unconstrained: bool = False
    alpha: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    margin_floor: float = Field(
        default=0.0,
        ge=0.0,
    )
    allocation_mode: str = "actual"
    q_splits: Optional[Dict[str, float]] = None


class PlanRequest(BaseModel):
    """Request model for future promotion planning."""

    economics: Literal["tn", "legacy"] = "tn"

    skus: List[str] = Field(
        ...,
        min_length=1,
        description="List of SKUs to simulate.",
    )
    plan_year: Optional[int] = Field(
        default=None,
        ge=2000,
    )
    base_year: Optional[int] = Field(
        default=None,
        ge=2000,
    )
    use_trend: bool = True
    objective: str = "profit"
    max_discount: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    budget_multiplier: float = Field(
        default=1.0,
        gt=0.0,
    )
    ref_year: Optional[int] = Field(
        default=None,
        ge=2000,
    )
    q_splits: Dict[str, float] = Field(
        default_factory=lambda: {
            "Q1": 25.0,
            "Q2": 25.0,
            "Q3": 25.0,
            "Q4": 25.0,
        }
    )
    unconstrained: bool = False
    alpha: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    margin_floor: float = Field(
        default=0.0,
        ge=0.0,
    )