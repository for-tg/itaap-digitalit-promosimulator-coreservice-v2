"""Database engine and session configuration.

Uses SQLite for local development and Azure PostgreSQL
for deployed environments.
"""

import logging
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config.settings import settings


logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy database models."""


def create_database_engine() -> Engine:
    """Create the SQLAlchemy database engine."""

    database_url = settings.DATABASE_URL
    logger.info(
        "Database URL generated. url=%s",
        database_url,
    )

    logger.info(
        "Database config. host=%s port=%s database=%s user=%s env=%s",
        settings.AWS_DB_HOST,
        settings.AWS_DB_PORT,
        settings.AWS_DB_NAME,
        settings.AWS_DB_USER,
        settings.APP_ENV,
    )


    if database_url.startswith("sqlite"):
        logger.info("Creating SQLite database engine.")

        return create_engine(
            database_url,
            connect_args={
                "check_same_thread": False,
            },
            pool_pre_ping=True,
        )

    logger.info(
        "Creating Azure PostgreSQL database engine for host=%s database=%s",
        settings.AWS_DB_HOST,
        settings.AWS_DB_NAME,
    )

    

    postgres_engine = create_engine(
        database_url,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=5,
        max_overflow=10,
        connect_args={
            "sslmode": "require",
        },
    )

    @event.listens_for(
        postgres_engine,
        "do_connect",
    )
    def provide_azure_access_token(
        _dialect,
        _connection_record,
        _connection_args,
        connection_params,
    ) -> None:
        logger.info(
            "SQLAlchemy do_connect event triggered."
        )

        token = settings.AWS_DB_PASSWORD

        logger.info(
            "Azure PostgreSQL access token generated. "
            "token_length=%s",
            len(token),
        )

        connection_params["password"] = token

        logger.info(
            "Password injected into PostgreSQL connection parameters."
        )

        logger.info(
            "Connection parameters after token injection. "
            "host=%s port=%s dbname=%s user=%s sslmode=%s",
            connection_params.get("host"),
            connection_params.get("port"),
            connection_params.get("dbname"),
            connection_params.get("user"),
            connection_params.get("sslmode"),
        )

    return postgres_engine


engine = create_database_engine()


SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Provide a database session and close it after the request."""

    database_session = SessionLocal()

    try:
        yield database_session

    except Exception:
        database_session.rollback()
        raise

    finally:
        database_session.close()