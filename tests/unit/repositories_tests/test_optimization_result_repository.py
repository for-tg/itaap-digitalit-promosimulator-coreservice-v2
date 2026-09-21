from unittest.mock import MagicMock, patch

from app.database.repositories.optimization_result_repository import (
    delete_optimization_result,
    get_optimization_result,
    upsert_optimization_result,
)


# ==========================================================
# get_optimization_result
# ==========================================================

def test_get_optimization_result():
    session = MagicMock()

    expected_result = MagicMock()

    session.scalar.return_value = expected_result

    result = get_optimization_result(
        database_session=session,
        scenario_id="scenario_1",
    )

    assert result == expected_result
    session.scalar.assert_called_once()


# ==========================================================
# upsert_optimization_result - create
# ==========================================================

@patch(
    "app.database.repositories.optimization_result_repository.OptimizationResult"
)
@patch(
    "app.database.repositories.optimization_result_repository.get_optimization_result"
)
def test_upsert_optimization_result_create(
    mock_get_optimization_result,
    mock_optimization_result,
):
    session = MagicMock()

    mock_get_optimization_result.return_value = None

    result_data = MagicMock()
    result_data.result_json = {"key": "value"}

    new_record = MagicMock()

    mock_optimization_result.return_value = new_record

    result = upsert_optimization_result(
        database_session=session,
        scenario_id="scenario_1",
        result_data=result_data,
    )

    assert result == new_record

    mock_optimization_result.assert_called_once_with(
        scenario_id="scenario_1",
        result_json={"key": "value"},
    )

    session.add.assert_called_once_with(
        new_record
    )
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(
        new_record
    )


# ==========================================================
# upsert_optimization_result - update
# ==========================================================

@patch(
    "app.database.repositories.optimization_result_repository.get_optimization_result"
)
def test_upsert_optimization_result_update(
    mock_get_optimization_result,
):
    session = MagicMock()

    existing_record = MagicMock()

    mock_get_optimization_result.return_value = (
        existing_record
    )

    result_data = MagicMock()
    result_data.result_json = {
        "updated": True
    }

    result = upsert_optimization_result(
        database_session=session,
        scenario_id="scenario_1",
        result_data=result_data,
    )

    assert result == existing_record
    assert (
        existing_record.result_json
        == {"updated": True}
    )

    session.add.assert_called_once_with(
        existing_record
    )
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(
        existing_record
    )


# ==========================================================
# delete_optimization_result
# ==========================================================

def test_delete_optimization_result():
    session = MagicMock()

    optimization_result = MagicMock()

    delete_optimization_result(
        database_session=session,
        optimization_result=optimization_result,
    )

    session.delete.assert_called_once_with(
        optimization_result
    )
    session.commit.assert_called_once()