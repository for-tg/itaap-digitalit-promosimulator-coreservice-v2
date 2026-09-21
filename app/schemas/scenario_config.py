"""Pydantic schemas for scenario configuration APIs."""

from datetime import datetime
from enum import Enum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class AnalysisType(str, Enum):
    """Supported analysis types."""

    RETRO = "retro"
    PLAN = "plan"


class ObjectiveType(str, Enum):
    """Supported optimization objectives."""

    PROFIT = "profit"
    TURNOVER = "turnover"


class EconomicsType(str, Enum):
    """Supported price reference modes."""

    TN = "tn"
    LEGACY = "legacy"


class AllocationMode(str, Enum):
    """Supported quarterly allocation modes."""

    ACTUAL = "actual"
    CUSTOM = "custom"


class ScenarioConfigUpsert(BaseModel):
    """Request schema for creating or updating scenario configuration."""

    analysis_type: AnalysisType
    objective: ObjectiveType = ObjectiveType.PROFIT
    economics: EconomicsType = EconomicsType.TN

    selected_skus: list[str] = Field(
        ...,
        min_length=1,
    )

    year: int | None = Field(
        default=None,
        ge=2000,
    )

    plan_year: int | None = Field(
        default=None,
        ge=2000,
    )

    base_year: int | None = Field(
        default=None,
        ge=2000,
    )

    reference_year: int = Field(
        default=2025,
        ge=2000,
    )

    period: str = Field(
        default="Full year",
        max_length=30,
    )

    use_trend: bool = True

    max_discount: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
    )

    budget_multiplier: float = Field(
        default=1.0,
        gt=0.0,
    )

    unconstrained: bool = False

    alpha: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    margin_floor: float = Field(
        default=0.0,
        ge=0.0,
    )

    allocation_mode: AllocationMode = AllocationMode.ACTUAL

    quarterly_splits: dict[str, float] = Field(
        default_factory=lambda: {
            "Q1": 25.0,
            "Q2": 25.0,
            "Q3": 25.0,
            "Q4": 25.0,
        }
    )

    @field_validator(
        "selected_skus",
        mode="before",
    )
    @classmethod
    def clean_skus(
        cls,
        value: list[str],
    ) -> list[str]:
        """Trim SKU values and remove duplicates."""

        if not value:
            return []

        cleaned_skus: list[str] = []

        for sku in value:
            cleaned_sku = str(sku).strip()

            if (
                cleaned_sku
                and cleaned_sku not in cleaned_skus
            ):
                cleaned_skus.append(
                    cleaned_sku
                )

        return cleaned_skus

    @field_validator(
        "period",
        mode="before",
    )
    @classmethod
    def clean_period(
        cls,
        value: str,
    ) -> str:
        """Trim the period value."""

        return str(value).strip()

    @field_validator(
        "quarterly_splits"
    )
    @classmethod
    def validate_quarterly_splits(
        cls,
        value: dict[str, float],
    ) -> dict[str, float]:
        """Validate quarterly allocation percentages."""

        expected_quarters = {
            "Q1",
            "Q2",
            "Q3",
            "Q4",
        }

        if (
            set(value.keys())
            != expected_quarters
        ):
            raise ValueError(
                "quarterly_splits must contain "
                "Q1, Q2, Q3, and Q4."
            )

        cleaned_splits = {
            quarter: float(percentage)
            for quarter, percentage
            in value.items()
        }

        if any(
            percentage < 0
            for percentage
            in cleaned_splits.values()
        ):
            raise ValueError(
                "Quarterly split percentages "
                "cannot be negative."
            )

        total_percentage = sum(
            cleaned_splits.values()
        )

        if (
            abs(
                total_percentage
                - 100.0
            )
            > 0.01
        ):
            raise ValueError(
                "Quarterly split percentages "
                "must total 100."
            )

        return cleaned_splits

    @model_validator(
        mode="after"
    )
    def validate_analysis_fields(
        self,
    ) -> "ScenarioConfigUpsert":
        """Validate fields based on analysis type."""

        if (
            self.analysis_type
            == AnalysisType.RETRO
        ):
            if self.year is None:
                raise ValueError(
                    "year is required when "
                    "analysis_type is 'retro'."
                )

        if (
            self.analysis_type
            == AnalysisType.PLAN
        ):
            if self.plan_year is None:
                raise ValueError(
                    "plan_year is required when "
                    "analysis_type is 'plan'."
                )

            if self.base_year is None:
                raise ValueError(
                    "base_year is required when "
                    "analysis_type is 'plan'."
                )

        return self


class ScenarioConfigResponse(
    ScenarioConfigUpsert
):
    """Response schema for scenario configuration."""

    scenario_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )