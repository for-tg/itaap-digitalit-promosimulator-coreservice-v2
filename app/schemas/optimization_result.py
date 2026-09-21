"""Pydantic schemas for optimization result APIs."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OptimizationResultUpsert(BaseModel):
    """Request schema for storing an optimization result."""

    result_json: dict[str, Any] = Field(
        ...,
        description="Complete optimization response JSON.",
    )


class OptimizationResultResponse(BaseModel):
    """Response schema for optimization results."""

    scenario_id: str
    result_json: dict[str, Any]

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )