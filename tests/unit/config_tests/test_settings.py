import os
from unittest.mock import MagicMock, patch

import pytest

from app.config.settings import (
    AccessTokenError,
    Settings,
    get_access_token,
    get_settings,
)


# ==========================================================
# get_access_token()
# ==========================================================

@patch("app.config.settings.msal.ConfidentialClientApplication")
def test_get_access_token_success(mock_app):
    """Should return access token when MSAL succeeds."""

    mock_instance = MagicMock()
    mock_instance.acquire_token_for_client.return_value = {
        "access_token": "test_token"
    }

    mock_app.return_value = mock_instance

    token = get_access_token(
        tenant_id="tenant",
        client_id="client",
        client_secret="secret",
    )

    assert token == "test_token"


@patch("app.config.settings.msal.ConfidentialClientApplication")
def test_get_access_token_missing_token(mock_app):
    """Should raise AccessTokenError when token is absent."""

    mock_instance = MagicMock()
    mock_instance.acquire_token_for_client.return_value = {
        "error": "invalid_client",
        "error_description": "Invalid secret",
    }

    mock_app.return_value = mock_instance

    with pytest.raises(AccessTokenError) as exc:
        get_access_token(
            tenant_id="tenant",
            client_id="client",
            client_secret="secret",
        )

    assert "Invalid secret" in str(exc.value)


@patch("app.config.settings.msal.ConfidentialClientApplication")
def test_get_access_token_exception(mock_app):
    """Should wrap unexpected exceptions."""

    mock_app.side_effect = Exception("Boom")

    with pytest.raises(AccessTokenError) as exc:
        get_access_token(
            tenant_id="tenant",
            client_id="client",
            client_secret="secret",
        )

    assert (
        str(exc.value)
        == "Unable to acquire Azure PostgreSQL access token."
    )


# ==========================================================
# DATABASE_URL
# ==========================================================

def test_database_url_local():
    """Local environment should use SQLite."""

    settings = Settings(APP_ENV="local")

    assert (
        settings.DATABASE_URL
        == "sqlite:///./promo_simulator.db"
    )


def test_database_url_non_local():
    """Non-local environment should use PostgreSQL."""

    settings = Settings(
        APP_ENV="dev",
        AWS_DB_USER="test_user",
        AWS_DB_HOST="host",
        AWS_DB_PORT="5432",
        AWS_DB_NAME="promodb",
    )

    url = settings.DATABASE_URL

    assert url.startswith("postgresql+psycopg://")
    assert "test_user@" in url
    assert "host:5432" in url
    assert "promodb" in url


def test_database_url_url_encoding():
    """Ensure username/database values are quoted."""

    settings = Settings(
        APP_ENV="dev",
        AWS_DB_USER="user with space",
        AWS_DB_NAME="db name",
        AWS_DB_HOST="host",
    )

    url = settings.DATABASE_URL

    assert "user%20with%20space" in url
    assert "db%20name" in url


# ==========================================================
# AWS_DB_PASSWORD
# ==========================================================

@patch("app.config.settings.get_access_token")
def test_aws_db_password_success(mock_token):
    """Should return generated token."""

    mock_token.return_value = "generated_token"

    settings = Settings(
        CLIENT_SECRET="abc123"
    )

    result = settings.AWS_DB_PASSWORD

    assert result == "generated_token"

    mock_token.assert_called_once()


def test_aws_db_password_missing_secret():
    """Should fail when secret is empty."""

    settings = Settings(
        CLIENT_SECRET=""
    )

    with pytest.raises(AccessTokenError) as exc:
        _ = settings.AWS_DB_PASSWORD

    assert "CLIENT_SECRET is not configured" in str(exc.value)


# ==========================================================
# test factory methods
# ==========================================================

def test_get_unit_test_settings():
    settings = Settings.get_unit_test_settings()

    assert settings.APP_ENV == "local"
    assert settings.APP_VERSION == "1.0.0-unit-test"
    assert settings.MODEL_SOURCE == "local"
    assert settings.SEND_TELEMETRY_DATA == "false"


def test_get_integration_test_settings():
    settings = Settings.get_integration_test_settings()

    assert settings.APP_ENV == "local"
    assert settings.APP_VERSION == "1.0.0-integration-test"
    assert settings.MODEL_SOURCE == "local"


# ==========================================================
# get_settings()
# ==========================================================

def test_get_settings_default(monkeypatch):
    """Normal execution should return Settings()."""

    monkeypatch.delenv(
        "UNIT_TESTING_MODE",
        raising=False,
    )

    monkeypatch.delenv(
        "INTEGRATION_TESTING_MODE",
        raising=False,
    )

    get_settings.cache_clear()

    settings = get_settings()

    assert isinstance(settings, Settings)


def test_get_settings_unit_testing(monkeypatch):
    monkeypatch.setenv(
        "UNIT_TESTING_MODE",
        "true",
    )

    monkeypatch.delenv(
        "INTEGRATION_TESTING_MODE",
        raising=False,
    )

    get_settings.cache_clear()

    settings = get_settings()

    assert settings.APP_VERSION == "1.0.0-unit-test"


def test_get_settings_integration_testing(monkeypatch):
    monkeypatch.delenv(
        "UNIT_TESTING_MODE",
        raising=False,
    )

    monkeypatch.setenv(
        "INTEGRATION_TESTING_MODE",
        "true",
    )

    get_settings.cache_clear()

    settings = get_settings()

    assert settings.APP_VERSION == "1.0.0-integration-test"


# ==========================================================
# cache coverage
# ==========================================================

def test_get_settings_cached(monkeypatch):
    monkeypatch.delenv(
        "UNIT_TESTING_MODE",
        raising=False,
    )

    monkeypatch.delenv(
        "INTEGRATION_TESTING_MODE",
        raising=False,
    )

    get_settings.cache_clear()

    settings1 = get_settings()
    settings2 = get_settings()

    assert settings1 is settings2