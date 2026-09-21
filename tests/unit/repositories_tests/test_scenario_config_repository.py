from unittest.mock import MagicMock, patch

from app.database.repositories.scenario_config_repository import (
    delete_config,
    get_config_by_scenario_id,
    upsert_config,
)


# ==========================================================
# get_config_by_scenario_id
# ==========================================================

def test_get_config_by_scenario_id():
    session = MagicMock()

    config = MagicMock()
    session.scalar.return_value = config

    result = get_config_by_scenario_id(
        database_session=session,
        scenario_id="scenario1",
    )

    assert result == config
    session.scalar.assert_called_once()


# ==========================================================
# upsert_config - create
# ==========================================================

@patch(
    "app.database.repositories.scenario_config_repository.ScenarioConfig"
)
@patch(
    "app.database.repositories.scenario_config_repository.get_config_by_scenario_id"
)
def test_upsert_config_create(
    mock_get_config,
    mock_scenario_config,
):
    session = MagicMock()

    mock_get_config.return_value = None

    config_data = MagicMock()
    config_data.model_dump.return_value = {
        "country": "NL",
        "retailer": "AH",
    }

    config_obj = MagicMock()
    mock_scenario_config.return_value = config_obj

    result = upsert_config(
        database_session=session,
        scenario_id="scenario1",
        config_data=config_data,
    )

    assert result == config_obj

    mock_scenario_config.assert_called_once_with(
        scenario_id="scenario1",
        country="NL",
        retailer="AH",
    )

    session.add.assert_called_once_with(config_obj)
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(config_obj)


# ==========================================================
# upsert_config - update
# ==========================================================

@patch(
    "app.database.repositories.scenario_config_repository.get_config_by_scenario_id"
)
def test_upsert_config_update(
    mock_get_config,
):
    session = MagicMock()

    existing_config = MagicMock()

    mock_get_config.return_value = existing_config

    config_data = MagicMock()
    config_data.model_dump.return_value = {
        "country": "FR",
        "retailer": "Carrefour",
    }

    result = upsert_config(
        database_session=session,
        scenario_id="scenario1",
        config_data=config_data,
    )

    assert result == existing_config
    assert existing_config.country == "FR"
    assert existing_config.retailer == "Carrefour"

    session.add.assert_called_once_with(
        existing_config
    )
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(
        existing_config
    )


# ==========================================================
# upsert_config - enum value handling
# ==========================================================

class DummyEnum:
    def __init__(self, value):
        self.value = value


@patch(
    "app.database.repositories.scenario_config_repository.get_config_by_scenario_id"
)
def test_upsert_config_updates_enum_values(
    mock_get_config,
):
    session = MagicMock()

    existing_config = MagicMock()

    mock_get_config.return_value = existing_config

    config_data = MagicMock()
    config_data.model_dump.return_value = {
        "status": DummyEnum("ACTIVE"),
    }

    result = upsert_config(
        database_session=session,
        scenario_id="scenario1",
        config_data=config_data,
    )

    assert result == existing_config
    assert existing_config.status == "ACTIVE"

    session.add.assert_called_once_with(
        existing_config
    )
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(
        existing_config
    )


# ==========================================================
# delete_config
# ==========================================================

def test_delete_config():
    session = MagicMock()

    config = MagicMock()

    delete_config(
        database_session=session,
        config=config,
    )

    session.delete.assert_called_once_with(config)
    session.commit.assert_called_once()