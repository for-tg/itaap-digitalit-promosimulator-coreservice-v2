"""Pydantic schemas for scenario APIs."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ScenarioStatus(str, Enum):
    """Supported scenario statuses."""

    DRAFT = "DRAFT"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ScenarioCreate(BaseModel):
    """Request schema for creating a scenario."""

    scenario_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )

    @field_validator(
        "scenario_name",
        mode="before",
    )
    @classmethod
    def trim_scenario_name(
        cls,
        value: str,
    ) -> str:
        """Trim the scenario name."""

        return str(value).strip()


class ScenarioUpdate(BaseModel):
    """Request schema for updating a scenario."""

    scenario_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    status: ScenarioStatus | None = None

    @field_validator(
        "scenario_name",
        mode="before",
    )
    @classmethod
    def trim_optional_name(
        cls,
        value: str | None,
    ) -> str | None:
        """Trim an optional scenario name."""

        if isinstance(value, str):
            return value.strip()

        return value


class ScenarioResponse(BaseModel):
    """Response schema for a scenario."""

    scenario_id: str
    project_id: str
    scenario_name: str
    status: ScenarioStatus
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


class ScenarioListResponse(BaseModel):
    """Response schema for listing scenarios."""

    total: int
    scenarios: list[ScenarioResponse]