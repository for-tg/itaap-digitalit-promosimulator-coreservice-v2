from unittest.mock import MagicMock, patch

import pytest

from app.config.database import (
    create_database_engine,
    get_db,
)


# ==========================================================
# create_database_engine() - SQLite
# ==========================================================

@patch("app.config.database.create_engine")
@patch("app.config.database.settings")
def test_create_database_engine_sqlite(
    mock_settings,
    mock_create_engine,
):
    mock_settings.DATABASE_URL = "sqlite:///test.db"

    engine_mock = MagicMock()
    mock_create_engine.return_value = engine_mock

    result = create_database_engine()

    assert result == engine_mock

    mock_create_engine.assert_called_once_with(
        "sqlite:///test.db",
        connect_args={
            "check_same_thread": False,
        },
        pool_pre_ping=True,
    )


# ==========================================================
# create_database_engine() - PostgreSQL
# ==========================================================

@patch("app.config.database.event.listens_for")
@patch("app.config.database.create_engine")
@patch("app.config.database.settings")
def test_create_database_engine_postgres(
    mock_settings,
    mock_create_engine,
    mock_listens_for,
):
    mock_settings.DATABASE_URL = (
        "postgresql+psycopg://user@host/db"
    )
    mock_settings.AWS_DB_HOST = "host"
    mock_settings.AWS_DB_NAME = "db"

    engine_mock = MagicMock()
    mock_create_engine.return_value = engine_mock

    # Mock decorator behavior
    mock_listens_for.return_value = lambda func: func

    result = create_database_engine()

    assert result == engine_mock

    mock_create_engine.assert_called_once_with(
        "postgresql+psycopg://user@host/db",
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=5,
        max_overflow=10,
        connect_args={
            "sslmode": "require",
        },
    )

    mock_listens_for.assert_called_once_with(
        engine_mock,
        "do_connect",
    )


# ==========================================================
# Event listener registration
# ==========================================================

@patch("app.config.database.event.listens_for")
@patch("app.config.database.create_engine")
@patch("app.config.database.settings")
def test_postgres_registers_listener(
    mock_settings,
    mock_create_engine,
    mock_listens_for,
):
    mock_settings.DATABASE_URL = (
        "postgresql+psycopg://user@host/db"
    )
    mock_settings.AWS_DB_HOST = "host"
    mock_settings.AWS_DB_NAME = "db"

    engine_mock = MagicMock()
    mock_create_engine.return_value = engine_mock

    captured_listener = None

    def decorator(*args, **kwargs):
        def wrapper(func):
            nonlocal captured_listener
            captured_listener = func
            return func

        return wrapper

    mock_listens_for.side_effect = decorator

    create_database_engine()

    assert captured_listener is not None


# ==========================================================
# Event listener injects password
# ==========================================================

@patch("app.config.database.event.listens_for")
@patch("app.config.database.create_engine")
@patch("app.config.database.settings")
def test_postgres_listener_sets_password(
    mock_settings,
    mock_create_engine,
    mock_listens_for,
):
    mock_settings.DATABASE_URL = (
        "postgresql+psycopg://user@host/db"
    )
    mock_settings.AWS_DB_HOST = "host"
    mock_settings.AWS_DB_NAME = "db"
    mock_settings.AWS_DB_PASSWORD = "fresh_token"

    engine_mock = MagicMock()
    mock_create_engine.return_value = engine_mock

    listener = None

    def decorator(*args, **kwargs):
        def wrapper(func):
            nonlocal listener
            listener = func
            return func

        return wrapper

    mock_listens_for.side_effect = decorator

    create_database_engine()

    assert listener is not None

    connection_params = {}

    listener(
        None,
        None,
        None,
        connection_params,
    )

    assert connection_params["password"] == "fresh_token"


# ==========================================================
# get_db() happy path
# ==========================================================

@patch("app.config.database.SessionLocal")
def test_get_db_success(
    mock_session_local,
):
    session_mock = MagicMock()

    mock_session_local.return_value = session_mock

    generator = get_db()

    session = next(generator)

    assert session == session_mock

    with pytest.raises(StopIteration):
        next(generator)

    session_mock.rollback.assert_not_called()
    session_mock.close.assert_called_once()


# ==========================================================
# get_db() rollback on exception
# ==========================================================

@patch("app.config.database.SessionLocal")
def test_get_db_exception_rolls_back(
    mock_session_local,
):
    session_mock = MagicMock()

    mock_session_local.return_value = session_mock

    generator = get_db()

    next(generator)

    with pytest.raises(RuntimeError):
        generator.throw(
            RuntimeError("Database failure")
        )

    session_mock.rollback.assert_called_once()
    session_mock.close.assert_called_once()


# ==========================================================
# get_db() always closes session
# ==========================================================

@patch("app.config.database.SessionLocal")
def test_get_db_always_closes(
    mock_session_local,
):
    session_mock = MagicMock()

    mock_session_local.return_value = session_mock

    generator = get_db()

    next(generator)

    try:
        next(generator)
    except StopIteration:
        pass

    session_mock.close.assert_called_once()