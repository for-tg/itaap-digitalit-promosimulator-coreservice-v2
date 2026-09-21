"""Database operations for scenario configurations."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.scenario_config import ScenarioConfig
from app.schemas.scenario_config import ScenarioConfigUpsert


def get_config_by_scenario_id(
    database_session: Session,
    scenario_id: str,
) -> ScenarioConfig | None:
    """Return the active configuration for a scenario."""

    statement = select(ScenarioConfig).where(
        ScenarioConfig.scenario_id == scenario_id
    )

    return database_session.scalar(statement)


def upsert_config(
    database_session: Session,
    scenario_id: str,
    config_data: ScenarioConfigUpsert,
) -> ScenarioConfig:
    """Create or update the active configuration for a scenario."""

    config = get_config_by_scenario_id(
        database_session=database_session,
        scenario_id=scenario_id,
    )

    config_values = config_data.model_dump()

    if config is None:
        config = ScenarioConfig(
            scenario_id=scenario_id,
            **config_values,
        )
    else:
        for field_name, field_value in config_values.items():
            if hasattr(field_value, "value"):
                field_value = field_value.value

            setattr(
                config,
                field_name,
                field_value,
            )

    database_session.add(config)
    database_session.commit()
    database_session.refresh(config)

    return config


def delete_config(
    database_session: Session,
    config: ScenarioConfig,
) -> None:
    """Delete a scenario configuration."""

    database_session.delete(config)
    database_session.commit()