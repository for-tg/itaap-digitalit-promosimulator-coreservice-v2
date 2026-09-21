"""Business logic for scenario configuration management."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database.repositories import (
    scenario_config_repository,
    scenario_repository,
)
from app.schemas.scenario_config import (
    ScenarioConfigResponse,
    ScenarioConfigUpsert,
)


def get_scenario_config(
    database_session: Session,
    scenario_id: str,
) -> ScenarioConfigResponse | None:
    """Return the active configuration for a scenario."""

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

    config = scenario_config_repository.get_config_by_scenario_id(
        database_session=database_session,
        scenario_id=cleaned_scenario_id,
    )

    if config is None:
        return None

    return ScenarioConfigResponse.model_validate(config)

def upsert_scenario_config(
    database_session: Session,
    scenario_id: str,
    config_data: ScenarioConfigUpsert,
) -> ScenarioConfigResponse:
    """Create or update the active configuration for a scenario."""

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

    config = scenario_config_repository.upsert_config(
        database_session=database_session,
        scenario_id=cleaned_scenario_id,
        config_data=config_data,
    )

    return ScenarioConfigResponse.model_validate(config)


def delete_scenario_config(
    database_session: Session,
    scenario_id: str,
) -> None:
    """Delete the active configuration for a scenario."""

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

    config = scenario_config_repository.get_config_by_scenario_id(
        database_session=database_session,
        scenario_id=cleaned_scenario_id,
    )

    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario configuration not found.",
        )

    scenario_config_repository.delete_config(
        database_session=database_session,
        config=config,
    )