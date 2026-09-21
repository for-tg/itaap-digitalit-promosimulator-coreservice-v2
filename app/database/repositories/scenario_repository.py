"""Database operations for scenarios."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.scenario import Scenario
from app.schemas.scenario import ScenarioCreate, ScenarioUpdate


def create_scenario(
    database_session: Session,
    project_id: str,
    scenario_data: ScenarioCreate,
) -> Scenario:
    """Create and save a new scenario."""

    scenario = Scenario(
        project_id=project_id,
        scenario_name=scenario_data.scenario_name,
    )

    database_session.add(scenario)
    database_session.commit()
    database_session.refresh(scenario)

    return scenario


def get_scenario_by_id(
    database_session: Session,
    scenario_id: str,
) -> Scenario | None:
    """Return one active scenario by ID."""

    statement = select(Scenario).where(
        Scenario.scenario_id == scenario_id,
        Scenario.is_deleted.is_(False),
    )

    return database_session.scalar(statement)


def list_scenarios_by_project(
    database_session: Session,
    project_id: str,
) -> list[Scenario]:
    """Return all active scenarios for a project."""

    statement = (
        select(Scenario)
        .where(
            Scenario.project_id == project_id,
            Scenario.is_deleted.is_(False),
        )
        .order_by(Scenario.updated_at.desc())
    )

    return list(
        database_session.scalars(statement).all()
    )


def list_deleted_scenarios_by_project(
    database_session: Session,
    project_id: str,
) -> list[Scenario]:
    """Return soft-deleted scenarios for a project."""

    statement = (
        select(Scenario)
        .where(
            Scenario.project_id == project_id,
            Scenario.is_deleted.is_(True),
        )
        .order_by(Scenario.updated_at.desc())
    )

    return list(
        database_session.scalars(statement).all()
    )


def get_scenario_by_id_including_deleted(
    database_session: Session,
    scenario_id: str,
) -> Scenario | None:
    """Return a scenario including soft-deleted records."""

    statement = select(Scenario).where(
        Scenario.scenario_id == scenario_id,
    )

    return database_session.scalar(statement)



def restore_scenario(
    database_session: Session,
    scenario: Scenario,
) -> Scenario:
    """Restore a soft-deleted scenario."""

    scenario.is_deleted = False

    database_session.add(scenario)
    database_session.commit()
    database_session.refresh(scenario)

    return scenario


def update_scenario(
    database_session: Session,
    scenario: Scenario,
    scenario_data: ScenarioUpdate,
) -> Scenario:
    """Update an existing scenario."""

    update_values = scenario_data.model_dump(
        exclude_unset=True,
    )

    for field_name, field_value in update_values.items():
        if field_name == "status" and field_value is not None:
            field_value = field_value.value

        setattr(
            scenario,
            field_name,
            field_value,
        )

    database_session.add(scenario)
    database_session.commit()
    database_session.refresh(scenario)

    return scenario


def soft_delete_scenario(
    database_session: Session,
    scenario: Scenario,
) -> Scenario:
    """Soft-delete a scenario."""

    scenario.is_deleted = True

    database_session.add(scenario)
    database_session.commit()
    database_session.refresh(scenario)

    return scenario


def scenario_name_exists_for_project(
    database_session: Session,
    project_id: str,
    scenario_name: str,
    exclude_scenario_id: str | None = None,
) -> bool:
    """Check whether an active scenario name exists in a project."""

    statement = select(Scenario.scenario_id).where(
        Scenario.project_id == project_id,
        Scenario.scenario_name == scenario_name,
        Scenario.is_deleted.is_(False),
    )

    if exclude_scenario_id:
        statement = statement.where(
            Scenario.scenario_id != exclude_scenario_id,
        )

    return database_session.scalar(statement) is not None

def update_scenario_status(
    database_session: Session,
    scenario: Scenario,
    scenario_status: str,
) -> Scenario:
    """Update the scenario execution status."""

    scenario.status = scenario_status

    database_session.add(scenario)
    database_session.commit()
    database_session.refresh(scenario)

    return scenario