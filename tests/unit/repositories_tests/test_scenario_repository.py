from unittest.mock import MagicMock, patch

from app.database.repositories.scenario_repository import (
    create_scenario,
    get_scenario_by_id,
    get_scenario_by_id_including_deleted,
    list_deleted_scenarios_by_project,
    list_scenarios_by_project,
    restore_scenario,
    scenario_name_exists_for_project,
    soft_delete_scenario,
    update_scenario,
    update_scenario_status,
)


# ==========================================================
# create_scenario
# ==========================================================

@patch(
    "app.database.repositories.scenario_repository.Scenario"
)
def test_create_scenario(mock_scenario):
    session = MagicMock()

    scenario_data = MagicMock()
    scenario_data.scenario_name = "Test Scenario"

    scenario_obj = MagicMock()
    mock_scenario.return_value = scenario_obj

    result = create_scenario(
        database_session=session,
        project_id="project1",
        scenario_data=scenario_data,
    )

    assert result == scenario_obj

    mock_scenario.assert_called_once_with(
        project_id="project1",
        scenario_name="Test Scenario",
    )

    session.add.assert_called_once_with(
        scenario_obj
    )
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(
        scenario_obj
    )


# ==========================================================
# get_scenario_by_id
# ==========================================================

def test_get_scenario_by_id():
    session = MagicMock()

    scenario = MagicMock()
    session.scalar.return_value = scenario

    result = get_scenario_by_id(
        database_session=session,
        scenario_id="scenario1",
    )

    assert result == scenario


# ==========================================================
# list_scenarios_by_project
# ==========================================================

def test_list_scenarios_by_project():
    session = MagicMock()

    scenarios = [MagicMock(), MagicMock()]
    session.scalars.return_value.all.return_value = (
        scenarios
    )

    result = list_scenarios_by_project(
        database_session=session,
        project_id="project1",
    )

    assert result == scenarios


# ==========================================================
# list_deleted_scenarios_by_project
# ==========================================================

def test_list_deleted_scenarios_by_project():
    session = MagicMock()

    scenarios = [MagicMock()]
    session.scalars.return_value.all.return_value = (
        scenarios
    )

    result = list_deleted_scenarios_by_project(
        database_session=session,
        project_id="project1",
    )

    assert result == scenarios


# ==========================================================
# get_scenario_by_id_including_deleted
# ==========================================================

def test_get_scenario_by_id_including_deleted():
    session = MagicMock()

    scenario = MagicMock()
    session.scalar.return_value = scenario

    result = get_scenario_by_id_including_deleted(
        database_session=session,
        scenario_id="scenario1",
    )

    assert result == scenario


# ==========================================================
# restore_scenario
# ==========================================================

def test_restore_scenario():
    session = MagicMock()

    scenario = MagicMock()
    scenario.is_deleted = True

    result = restore_scenario(
        database_session=session,
        scenario=scenario,
    )

    assert result == scenario
    assert scenario.is_deleted is False

    session.add.assert_called_once_with(
        scenario
    )
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(
        scenario
    )


# ==========================================================
# update_scenario
# ==========================================================

def test_update_scenario():
    session = MagicMock()

    scenario = MagicMock()

    scenario_data = MagicMock()
    scenario_data.model_dump.return_value = {
        "scenario_name": "Updated Scenario",
        "description": "Updated Desc",
    }

    result = update_scenario(
        database_session=session,
        scenario=scenario,
        scenario_data=scenario_data,
    )

    assert result == scenario
    assert scenario.scenario_name == (
        "Updated Scenario"
    )
    assert scenario.description == (
        "Updated Desc"
    )

    session.add.assert_called_once_with(
        scenario
    )
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(
        scenario
    )


# ==========================================================
# update_scenario status enum branch
# ==========================================================

class DummyStatus:
    value = "COMPLETED"


def test_update_scenario_status_enum():
    session = MagicMock()

    scenario = MagicMock()

    scenario_data = MagicMock()
    scenario_data.model_dump.return_value = {
        "status": DummyStatus(),
    }

    result = update_scenario(
        database_session=session,
        scenario=scenario,
        scenario_data=scenario_data,
    )

    assert result == scenario
    assert scenario.status == "COMPLETED"

    session.add.assert_called_once_with(
        scenario
    )


# ==========================================================
# update_scenario empty fields
# ==========================================================

def test_update_scenario_no_updates():
    session = MagicMock()

    scenario = MagicMock()

    scenario_data = MagicMock()
    scenario_data.model_dump.return_value = {}

    result = update_scenario(
        database_session=session,
        scenario=scenario,
        scenario_data=scenario_data,
    )

    assert result == scenario

    session.add.assert_called_once_with(
        scenario
    )
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(
        scenario
    )


# ==========================================================
# soft_delete_scenario
# ==========================================================

def test_soft_delete_scenario():
    session = MagicMock()

    scenario = MagicMock()

    result = soft_delete_scenario(
        database_session=session,
        scenario=scenario,
    )

    assert result == scenario
    assert scenario.is_deleted is True

    session.add.assert_called_once_with(
        scenario
    )
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(
        scenario
    )


# ==========================================================
# scenario_name_exists_for_project
# ==========================================================

def test_scenario_name_exists_true():
    session = MagicMock()

    session.scalar.return_value = (
        "scenario-id"
    )

    result = scenario_name_exists_for_project(
        database_session=session,
        project_id="project1",
        scenario_name="Scenario A",
    )

    assert result is True


def test_scenario_name_exists_false():
    session = MagicMock()

    session.scalar.return_value = None

    result = scenario_name_exists_for_project(
        database_session=session,
        project_id="project1",
        scenario_name="Scenario A",
    )

    assert result is False


def test_scenario_name_exists_exclude_id():
    session = MagicMock()

    session.scalar.return_value = (
        "another-id"
    )

    result = scenario_name_exists_for_project(
        database_session=session,
        project_id="project1",
        scenario_name="Scenario A",
        exclude_scenario_id="scenario123",
    )

    assert result is True


# ==========================================================
# update_scenario_status
# ==========================================================

def test_update_scenario_status():
    session = MagicMock()

    scenario = MagicMock()

    result = update_scenario_status(
        database_session=session,
        scenario=scenario,
        scenario_status="RUNNING",
    )

    assert result == scenario
    assert scenario.status == "RUNNING"

    session.add.assert_called_once_with(
        scenario
    )
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(
        scenario
    )