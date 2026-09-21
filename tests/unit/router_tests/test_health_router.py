from unittest.mock import MagicMock, patch

from sqlalchemy.exc import SQLAlchemyError

from app.routers.health_router import (
    _get_database_health,
    health,
)


# ==========================================================
# _get_database_health
# ==========================================================

def test_get_database_health_sqlite():
    connection = MagicMock()

    engine_mock = MagicMock()

    engine_mock.connect.return_value.__enter__.return_value = (
        connection
    )
    engine_mock.dialect.name = "sqlite"

    with patch(
        "app.routers.health_router.engine",
        engine_mock,
    ):
        result = _get_database_health()

    assert result == {
        "status": "connected",
        "type": "sqlite",
    }

    connection.execute.assert_called_once()


def test_get_database_health_postgres():
    connection = MagicMock()

    engine_mock = MagicMock()

    engine_mock.connect.return_value.__enter__.return_value = (
        connection
    )
    engine_mock.dialect.name = "postgresql"

    with patch(
        "app.routers.health_router.engine",
        engine_mock,
    ):
        result = _get_database_health()

    assert result == {
        "status": "connected",
        "type": "postgresql",
    }


def test_get_database_health_error():
    engine_mock = MagicMock()

    engine_mock.connect.side_effect = SQLAlchemyError(
        "Database unavailable"
    )
    engine_mock.dialect.name = "postgresql"

    with patch(
        "app.routers.health_router.engine",
        engine_mock,
    ):
        result = _get_database_health()

    assert result["status"] == "disconnected"
    assert result["type"] == "postgresql"
    assert "Database unavailable" in result["error"]


# ==========================================================
# health() - engine loading
# ==========================================================

@patch("app.routers.health_router.promo_engine")
@patch("app.routers.health_router._get_database_health")
@patch("app.routers.health_router.settings")
def test_health_loading(
    mock_settings,
    mock_db_health,
    mock_promo_engine,
):
    mock_settings.APP_NAME = "Promo Simulator"
    mock_settings.APP_VERSION = "1.0.0"
    mock_settings.APP_ENV = "local"

    mock_db_health.return_value = {
        "status": "connected",
        "type": "sqlite",
    }

    mock_promo_engine.is_ready.return_value = False

    result = health()

    assert result == {
        "status": "loading",
        "application": "Promo Simulator",
        "version": "1.0.0",
        "environment": "local",
        "database": {
            "status": "connected",
            "type": "sqlite",
        },
        "engine_ready": False,
        "skus_in_data": 0,
        "data_years": "",
        "n_years": 0,
    }


# ==========================================================
# health() - engine ready + connected db
# ==========================================================

@patch("app.routers.health_router._train_yr_str")
@patch("app.routers.health_router._get_train_years")
@patch("app.routers.health_router.promo_engine")
@patch("app.routers.health_router._get_database_health")
@patch("app.routers.health_router.settings")
def test_health_ok(
    mock_settings,
    mock_db_health,
    mock_promo_engine,
    mock_get_train_years,
    mock_train_yr_str,
):
    mock_settings.APP_NAME = "Promo Simulator"
    mock_settings.APP_VERSION = "1.0.0"
    mock_settings.APP_ENV = "dev"

    mock_db_health.return_value = {
        "status": "connected",
        "type": "postgresql",
    }

    mock_promo_engine.is_ready.return_value = True

    panel_df = MagicMock()
    panel_df["SKU"].nunique.return_value = 25
    mock_promo_engine.panel_df = panel_df

    mock_get_train_years.return_value = [
        2023,
        2024,
        2025,
    ]

    mock_train_yr_str.return_value = (
        "2023-2025"
    )

    result = health()

    assert result["status"] == "ok"
    assert result["engine_ready"] is True
    assert result["skus_in_data"] == 25
    assert result["data_years"] == "2023-2025"
    assert result["n_years"] == 3


# ==========================================================
# health() - engine ready + disconnected db
# ==========================================================

@patch("app.routers.health_router._train_yr_str")
@patch("app.routers.health_router._get_train_years")
@patch("app.routers.health_router.promo_engine")
@patch("app.routers.health_router._get_database_health")
@patch("app.routers.health_router.settings")
def test_health_degraded(
    mock_settings,
    mock_db_health,
    mock_promo_engine,
    mock_get_train_years,
    mock_train_yr_str,
):
    mock_settings.APP_NAME = "Promo Simulator"
    mock_settings.APP_VERSION = "1.0.0"
    mock_settings.APP_ENV = "dev"

    mock_db_health.return_value = {
        "status": "disconnected",
        "type": "postgresql",
        "error": "Connection failed",
    }

    mock_promo_engine.is_ready.return_value = True

    panel_df = MagicMock()
    panel_df["SKU"].nunique.return_value = 10
    mock_promo_engine.panel_df = panel_df

    mock_get_train_years.return_value = [
        2024,
        2025,
    ]

    mock_train_yr_str.return_value = (
        "2024-2025"
    )

    result = health()

    assert result["status"] == "degraded"
    assert result["engine_ready"] is True
    assert result["skus_in_data"] == 10
    assert result["n_years"] == 2