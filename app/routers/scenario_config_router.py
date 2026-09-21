"""Scenario configuration API routes."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.schemas.scenario_config import (
    ScenarioConfigResponse,
    ScenarioConfigUpsert,
)
from app.services import scenario_config_service


router = APIRouter(
    prefix="/api/scenarios",
    tags=["Scenario Configuration"],
)


@router.get(
    "/{scenario_id}/config",
    response_model=ScenarioConfigResponse | None,
    summary="Get scenario configuration",
)
def get_scenario_config(
    scenario_id: str,
    database_session: Session = Depends(get_db),
) -> ScenarioConfigResponse | None:
    """Return the active configuration for a scenario."""

    return scenario_config_service.get_scenario_config(
        database_session=database_session,
        scenario_id=scenario_id,
    )

@router.put(
    "/{scenario_id}/config",
    response_model=ScenarioConfigResponse,
    summary="Create or update scenario configuration",
)
def upsert_scenario_config(
    scenario_id: str,
    config_data: ScenarioConfigUpsert,
    database_session: Session = Depends(get_db),
) -> ScenarioConfigResponse:
    """Create or update the active configuration for a scenario."""

    return scenario_config_service.upsert_scenario_config(
        database_session=database_session,
        scenario_id=scenario_id,
        config_data=config_data,
    )


@router.delete(
    "/{scenario_id}/config",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete scenario configuration",
)
def delete_scenario_config(
    scenario_id: str,
    database_session: Session = Depends(get_db),
) -> Response:
    """Delete the active configuration for a scenario."""

    scenario_config_service.delete_scenario_config(
        database_session=database_session,
        scenario_id=scenario_id,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )