"""Scenario API routes."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.schemas.scenario import (
    ScenarioCreate,
    ScenarioListResponse,
    ScenarioResponse,
    ScenarioUpdate,
)
from app.services import scenario_service


router = APIRouter(
    tags=["Scenarios"],
)


@router.post(
    "/api/projects/{project_id}/scenarios",
    response_model=ScenarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a scenario",
)
def create_scenario(
    project_id: str,
    scenario_data: ScenarioCreate,
    database_session: Session = Depends(get_db),
) -> ScenarioResponse:
    """Create a scenario under a project."""

    return scenario_service.create_scenario(
        database_session=database_session,
        project_id=project_id,
        scenario_data=scenario_data,
    )


@router.get(
    "/api/projects/{project_id}/scenarios",
    response_model=ScenarioListResponse,
    summary="List project scenarios",
)
def list_scenarios(
    project_id: str,
    database_session: Session = Depends(get_db),
) -> ScenarioListResponse:
    """Return all active scenarios under a project."""

    return scenario_service.list_scenarios(
        database_session=database_session,
        project_id=project_id,
    )


@router.get(
    "/api/scenarios/{scenario_id}",
    response_model=ScenarioResponse,
    summary="Get a scenario",
)
def get_scenario(
    scenario_id: str,
    database_session: Session = Depends(get_db),
) -> ScenarioResponse:
    """Return one active scenario."""

    return scenario_service.get_scenario(
        database_session=database_session,
        scenario_id=scenario_id,
    )


@router.put(
    "/api/scenarios/{scenario_id}",
    response_model=ScenarioResponse,
    summary="Update a scenario",
)
def update_scenario(
    scenario_id: str,
    scenario_data: ScenarioUpdate,
    database_session: Session = Depends(get_db),
) -> ScenarioResponse:
    """Update a scenario."""

    return scenario_service.update_scenario(
        database_session=database_session,
        scenario_id=scenario_id,
        scenario_data=scenario_data,
    )


@router.delete(
    "/api/scenarios/{scenario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a scenario",
)
def delete_scenario(
    scenario_id: str,
    database_session: Session = Depends(get_db),
) -> Response:
    """Soft-delete a scenario."""

    scenario_service.delete_scenario(
        database_session=database_session,
        scenario_id=scenario_id,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )


@router.get(
    "/projects/{project_id}/scenarios/deleted",
    response_model=ScenarioListResponse,
    summary="List deleted scenarios",
)
def list_deleted_scenarios(
    project_id: str,
    database_session: Session = Depends(get_db),
) -> ScenarioListResponse:
    """Return soft-deleted scenarios for a project."""

    return scenario_service.list_deleted_scenarios(
        database_session=database_session,
        project_id=project_id,
    )



@router.post(
    "/scenarios/{scenario_id}/restore",
    response_model=ScenarioResponse,
    summary="Restore deleted scenario",
)
def restore_scenario(
    scenario_id: str,
    database_session: Session = Depends(get_db),
) -> ScenarioResponse:
    """Restore a soft-deleted scenario."""

    return scenario_service.restore_scenario(
        database_session=database_session,
        scenario_id=scenario_id,
    )