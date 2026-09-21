"""Business logic for scenario management."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database.models.scenario import Scenario
from app.database.repositories import (
    project_repository,
    scenario_repository,
)
from app.schemas.scenario import (
    ScenarioCreate,
    ScenarioListResponse,
    ScenarioResponse,
    ScenarioUpdate,
)


def create_scenario(
    database_session: Session,
    project_id: str,
    scenario_data: ScenarioCreate,
) -> ScenarioResponse:
    """Create a scenario under an existing project."""

    project = project_repository.get_project_by_id(
        database_session=database_session,
        project_id=project_id.strip(),
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    name_exists = scenario_repository.scenario_name_exists_for_project(
        database_session=database_session,
        project_id=project.project_id,
        scenario_name=scenario_data.scenario_name,
    )

    if name_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A scenario with this name already exists "
                "for the selected project."
            ),
        )

    scenario = scenario_repository.create_scenario(
        database_session=database_session,
        project_id=project.project_id,
        scenario_data=scenario_data,
    )

    return ScenarioResponse.model_validate(scenario)


def get_scenario(
    database_session: Session,
    scenario_id: str,
) -> ScenarioResponse:
    """Return one active scenario."""

    scenario = _get_existing_scenario(
        database_session=database_session,
        scenario_id=scenario_id,
    )

    return ScenarioResponse.model_validate(scenario)


def list_scenarios(
    database_session: Session,
    project_id: str,
) -> ScenarioListResponse:
    """Return all active scenarios for a project."""

    cleaned_project_id = project_id.strip()

    project = project_repository.get_project_by_id(
        database_session=database_session,
        project_id=cleaned_project_id,
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    scenarios = scenario_repository.list_scenarios_by_project(
        database_session=database_session,
        project_id=cleaned_project_id,
    )

    scenario_responses = [
        ScenarioResponse.model_validate(scenario)
        for scenario in scenarios
    ]

    return ScenarioListResponse(
        total=len(scenario_responses),
        scenarios=scenario_responses,
    )


def update_scenario(
    database_session: Session,
    scenario_id: str,
    scenario_data: ScenarioUpdate,
) -> ScenarioResponse:
    """Update an existing scenario."""

    scenario = _get_existing_scenario(
        database_session=database_session,
        scenario_id=scenario_id,
    )

    update_values = scenario_data.model_dump(
        exclude_unset=True,
    )

    if not update_values:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided for update.",
        )

    if (
        scenario_data.scenario_name is not None
        and scenario_data.scenario_name != scenario.scenario_name
    ):
        name_exists = (
            scenario_repository.scenario_name_exists_for_project(
                database_session=database_session,
                project_id=scenario.project_id,
                scenario_name=scenario_data.scenario_name,
                exclude_scenario_id=scenario.scenario_id,
            )
        )

        if name_exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A scenario with this name already exists "
                    "for the selected project."
                ),
            )

    updated_scenario = scenario_repository.update_scenario(
        database_session=database_session,
        scenario=scenario,
        scenario_data=scenario_data,
    )

    return ScenarioResponse.model_validate(updated_scenario)


def delete_scenario(
    database_session: Session,
    scenario_id: str,
) -> None:
    """Soft-delete an existing scenario."""

    scenario = _get_existing_scenario(
        database_session=database_session,
        scenario_id=scenario_id,
    )

    scenario_repository.soft_delete_scenario(
        database_session=database_session,
        scenario=scenario,
    )


def _get_existing_scenario(
    database_session: Session,
    scenario_id: str,
) -> Scenario:
    """Return an active scenario or raise a 404 error."""

    cleaned_scenario_id = scenario_id.strip()

    if not cleaned_scenario_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scenario_id must not be empty.",
        )

    scenario = scenario_repository.get_scenario_by_id(
        database_session=database_session,
        scenario_id=cleaned_scenario_id,
    )

    if scenario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found.",
        )

    return scenario



def list_deleted_scenarios(
    database_session: Session,
    project_id: str,
) -> ScenarioListResponse:
    """Return deleted scenarios for a project."""

    cleaned_project_id = project_id.strip()

    if not cleaned_project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project_id must not be empty.",
        )

    project = project_repository.get_project_by_id(
        database_session=database_session,
        project_id=cleaned_project_id,
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    scenarios = (
        scenario_repository.list_deleted_scenarios_by_project(
            database_session=database_session,
            project_id=cleaned_project_id,
        )
    )

    responses = [
        ScenarioResponse.model_validate(scenario)
        for scenario in scenarios
    ]

    return ScenarioListResponse(
        total=len(responses),
        scenarios=responses,
    )



def restore_scenario(
    database_session: Session,
    scenario_id: str,
) -> ScenarioResponse:
    """Restore a soft-deleted scenario."""

    cleaned_scenario_id = scenario_id.strip()

    if not cleaned_scenario_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scenario_id must not be empty.",
        )

    scenario = (
        scenario_repository.get_scenario_by_id_including_deleted(
            database_session=database_session,
            scenario_id=cleaned_scenario_id,
        )
    )

    if scenario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found.",
        )

    if not scenario.is_deleted:
        return ScenarioResponse.model_validate(scenario)

    restored_scenario = scenario_repository.restore_scenario(
        database_session=database_session,
        scenario=scenario,
    )

    return ScenarioResponse.model_validate(
        restored_scenario
    )