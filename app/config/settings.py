"""
Application configuration management.

Settings are loaded in the following priority order:

1. Environment variables
2. Values from the project .env file
3. Default values defined in the Settings class
"""

import logging
import os
from functools import lru_cache
from urllib.parse import quote

import msal
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


logger = logging.getLogger(__name__)


class AccessTokenError(Exception):
    """Raised when an Azure PostgreSQL access token cannot be retrieved."""


def get_access_token(
    tenant_id: str,
    client_id: str,
    client_secret: str,
) -> str:
    """Generate a fresh Azure PostgreSQL access token."""

    logger.info(
        "Requesting Azure PostgreSQL access token."
    )

    authority = (
        f"https://login.microsoftonline.com/{tenant_id}"
    )

    scopes = [
        "https://ossrdbms-aad.database.windows.net/.default"
    ]

    try:
        application = msal.ConfidentialClientApplication(
            client_id=client_id,
            authority=authority,
            client_credential=client_secret,
        )

        result = application.acquire_token_for_client(
            scopes=scopes,
        )

        access_token = result.get(
            "access_token"
        )

        if access_token:
            logger.info(
                "Azure PostgreSQL access token acquired successfully."
            )
            logger.info(
                "Azure PostgreSQL token acquired. "
                "token_length=%s",
                len(access_token),
            )

            return access_token

        error_description = result.get(
            "error_description",
            "Unable to acquire Azure PostgreSQL access token.",
        )

        logger.error(
            "Failed to obtain Azure PostgreSQL access token. "
            "Error=%s Description=%s",
            result.get("error"),
            error_description,
        )

        raise AccessTokenError(
            error_description
        )

    except AccessTokenError:
        raise

    except Exception as exc:
        logger.exception(
            "Exception while acquiring Azure PostgreSQL access token."
        )

        raise AccessTokenError(
            "Unable to acquire Azure PostgreSQL access token."
        ) from exc


class Settings(BaseSettings):
    """Application settings for the Promo Simulator backend."""

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------

    APP_NAME: str = (
        "itaap-digitalit-promosimulator-coreservice"
    )

    APP_ENV: str = "local"

    APP_VERSION: str = "1.0.0"

    LOG_LEVEL_APP: str = "INFO"

    ENABLE_AUTH: bool = True

        # ------------------------------------------------------------------
    # Databricks / ADL RBAC master-data source-1
    # ------------------------------------------------------------------

    # Temporary hardcoded values for development/testing.
    # Move these to Kubernetes/pipeline secrets before deployment.

    USE_DATABRICKS_RBAC: bool = True

    DATABRICKS_SERVER_HOSTNAME: str = (
        "adb-4245480955079103.3.azuredatabricks.net"
        # "adb-57587655985030.10.azuredatabricks.net"
    )

    DATABRICKS_HTTP_PATH: str = (
        "/sql/1.0/warehouses/d7a5402ba29d2ada"
        # "/sql/1.0/warehouses/a672f321ff3b064e"
    )

    DATABRICKS_CLIENT_ID: str = (
        "a6c9583e-fe4d-423f-b04d-cfa7b7ba5af1"
        # "de68c2e6-9574-47a8-b9cd-65ebeb33c8ac"
    )

    DATABRICKS_CLIENT_SECRET: SecretStr = SecretStr(
        "WXk8Q~fvAURd8LhQ6YC_bBc4vwFRyHTEiIIBObc2"
        # "3EP8Q~dqtlKSTzCNSFdRCo4T_oiQ01D6HOd.WaEh"
    )

    TENANT_ID: str = (
        "1a407a2d-7675-4d17-8692-b3ac285306e4"
    )



    DATABRICKS_TOKEN_URL: str = (
        "https://login.microsoftonline.com/"
        f"{TENANT_ID}/oauth2/v2.0/token"
    )

    DATABRICKS_SCOPE: str = (
        "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d/.default"
    )

    # DATABRICKS_CATALOG: str = ( -1
    #     "promo_simulator"
    # )

    # DATABRICKS_SCHEMA: str = (
    #     "rbac"
    # )

    # RBAC_REGION_COUNTRY_MASTER_TABLE: str = (
    #     "rbac_region_country_master"
    # )

    # RBAC_REGION_COUNTRY_MAPPING_TABLE: str = (
    #     "rbac_region_country_mapping"
    # )

    DATABRICKS_CATALOG: str = "dev_wb"
    DATABRICKS_SCHEMA: str = "phcom"

    RBAC_REGION_COUNTRY_MASTER_TABLE: str = (
        "tbl_regions_countries_master"
    )

    RBAC_REGION_COUNTRY_MAPPING_TABLE: str = (
        "promo_master_mappings"
    )

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    JWT_AUDIENCE: str = (
        "api://itaap-digitalit-promosimulator-frontend-non-prod"
        # "api://itaap-digitalit-promosimulator-backend-non-prod/.default"
    )

    JWKS_URL: str = (
        "https://login.microsoftonline.com/"
        "1a407a2d-7675-4d17-8692-b3ac285306e4/"
        "discovery/v2.0/keys"
    )

    TENANT_ID: str = (
        "1a407a2d-7675-4d17-8692-b3ac285306e4"
    )

    SAMPLE_API_ROLE: str = "api.status"

    #encryption
    ENCRYPTION_KEY :SecretStr = SecretStr("QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVowMTIzNDU=")

    # ------------------------------------------------------------------
    # Telemetry
    # ------------------------------------------------------------------

    SEND_TELEMETRY_DATA: str = "true"

    ELASTICSEARCH_URL: str = ""

    ELASTICSEARCH_USERNAME: str = ""

    ELASTICSEARCH_PASSWORD: str = ""

    ELASTIC_INDEX_PREFIX: str = (
        "itaap-digitalit-promosimulator-coreservice"
    )

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    #
    # APP_ENV=local
    #     -> SQLite
    #
    # Any other APP_ENV
    #     -> Azure PostgreSQL
    # ------------------------------------------------------------------

    # Azure Service Principal created for Promo Simulator PostgreSQL.
    CLIENT_ID: str = (
        "fc4593b2-150e-4a24-a782-a296db8f4841"
    )

    # Temporary development value.
    # Replace with the PostgreSQL service-principal secret you already use.
    CLIENT_SECRET: SecretStr = SecretStr(
        "bBt8Q~JzwailpPexgrbdyNOPOKvbVeWzeBiH9cUx"
    )

    # PostgreSQL Microsoft Entra principal.
    AWS_DB_USER: str = (
        "DEV AZ25D1-Digital-PHCommercial-posgressql"
    )

    AWS_DB_HOST: str = (
        "phpadgenaidbdev.postgres.database.azure.com"
    )

    AWS_DB_PORT: str = "5432"

    AWS_DB_NAME: str = "promodev"

    @property
    def DATABASE_URL(self) -> str:
        """Return SQLite locally or Azure PostgreSQL in deployments."""

        if self.APP_ENV.lower() == "local":
            logger.info(
                "Local environment detected. Using SQLite database."
            )

            return "sqlite:///./promo_simulator.db"

        logger.info(
            "Deployment environment detected. "
            "Using Azure PostgreSQL host=%s database=%s user=%s",
            self.AWS_DB_HOST,
            self.AWS_DB_NAME,
            self.AWS_DB_USER,
        )
        logger.info(
            "Database configuration. "
            "host=%s port=%s database=%s user=%s env=%s",
            self.AWS_DB_HOST,
            self.AWS_DB_PORT,
            self.AWS_DB_NAME,
            self.AWS_DB_USER,
            self.APP_ENV,
        )

        return (
            "postgresql+psycopg://"
            f"{quote(self.AWS_DB_USER)}@"
            f"{self.AWS_DB_HOST}:"
            f"{self.AWS_DB_PORT}/"
            f"{quote(self.AWS_DB_NAME)}"
        )

    @property
    def AWS_DB_PASSWORD(self) -> str:
        """Generate a fresh Azure PostgreSQL access token."""

        logger.info(
            "Generating Azure PostgreSQL database access token."
        )

        client_secret = (
            self.CLIENT_SECRET.get_secret_value().strip()
        )

        if not client_secret:
            raise AccessTokenError(
                "CLIENT_SECRET is not configured."
            )

        return get_access_token(
            tenant_id=self.TENANT_ID,
            client_id=self.CLIENT_ID,
            client_secret=client_secret,
        )

    # ------------------------------------------------------------------
    # Model source
    # ------------------------------------------------------------------

    MODEL_SOURCE: str = "local"

    # ------------------------------------------------------------------
    # S3 model configuration
    # ------------------------------------------------------------------

    AWS_REGION: str = "eu-west-1"

    S3_BUCKET_NAME: str = (
        "itaap-digitalit--non-prod--generic-usage"
    )

    S3_MODEL_PREFIX: str = (
        "dev/promosimulator-coreservice/"
        "model-pickelfile/"
    )

    S3_MODEL_KEY: str = ""

    # ------------------------------------------------------------------
    # Local model configuration
    # ------------------------------------------------------------------

    LOCAL_MODEL_PATH: str = (
        "DE_AMAZON_RTB.pkl"
    )

    COGS_CSV_PATH: str = (
        "COGS_per_SKU.csv"
    )

    # ------------------------------------------------------------------
    # Pydantic settings configuration
    # ------------------------------------------------------------------

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow",
    )

    # ------------------------------------------------------------------
    # Unit test configuration
    # ------------------------------------------------------------------

    @classmethod
    def get_unit_test_settings(
        cls,
    ) -> "Settings":
        """Create settings for unit tests."""

        return cls(
            APP_ENV="local",
            APP_VERSION="1.0.0-unit-test",
            MODEL_SOURCE="local",
            ELASTICSEARCH_URL="dummy_url",
            ELASTICSEARCH_USERNAME="dummy_username",
            ELASTICSEARCH_PASSWORD="dummy_password",
            SEND_TELEMETRY_DATA="false",
            S3_BUCKET_NAME="",
            S3_MODEL_PREFIX="",
            S3_MODEL_KEY="",
        )

    # ------------------------------------------------------------------
    # Integration test configuration
    # ------------------------------------------------------------------

    @classmethod
    def get_integration_test_settings(
        cls,
    ) -> "Settings":
        """Create settings for integration tests."""

        return cls(
            APP_ENV="local",
            APP_VERSION="1.0.0-integration-test",
            MODEL_SOURCE="local",
            S3_BUCKET_NAME="",
            S3_MODEL_PREFIX="",
            S3_MODEL_KEY="",
        )


@lru_cache
def get_settings() -> Settings:
    """Return settings for the current execution mode."""

    if (
        os.environ.get(
            "UNIT_TESTING_MODE",
            "",
        ).lower()
        == "true"
    ):
        return Settings.get_unit_test_settings()

    if (
        os.environ.get(
            "INTEGRATION_TESTING_MODE",
            "",
        ).lower()
        == "true"
    ):
        return Settings.get_integration_test_settings()

    return Settings()


settings = get_settings()
