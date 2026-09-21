"""Scenario optimization workflow API routes."""

from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.services import scenario_optimization_service


router = APIRouter(
    prefix="/api/scenarios",
    tags=["Scenario Optimization"],
)


@router.post(
    "/{scenario_id}/optimize",
    status_code=status.HTTP_200_OK,
    summary="Run scenario optimization",
)
def optimize_scenario(
    scenario_id: str,
    database_session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Run optimization using the saved scenario configuration."""

    return scenario_optimization_service.optimize_scenario(
        database_session=database_session,
        scenario_id=scenario_id,
    )