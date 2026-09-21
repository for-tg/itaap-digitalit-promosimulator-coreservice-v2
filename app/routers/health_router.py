"""Health check endpoint."""

from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config.database import engine
from app.config.settings import settings
from app.engine import promo_engine
from app.services.simulation_service import (
    _get_train_years,
    _train_yr_str,
)


router = APIRouter()


def _get_database_health() -> dict:
    """Check database connectivity and return database status."""

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        database_type = (
            "sqlite"
            if engine.dialect.name == "sqlite"
            else "postgresql"
        )

        return {
            "status": "connected",
            "type": database_type,
        }

    except SQLAlchemyError as exc:
        return {
            "status": "disconnected",
            "type": engine.dialect.name,
            "error": str(exc),
        }


@router.get("/api/health")
def health() -> dict:
    """Return application, database, and promotion engine health status."""

    database_health = _get_database_health()

    engine_ready = promo_engine.is_ready()

    if not engine_ready:
        return {
            "status": "loading",
            "application": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.APP_ENV,
            "database": database_health,
            "engine_ready": False,
            "skus_in_data": 0,
            "data_years": "",
            "n_years": 0,
        }

    training_years = _get_train_years()

    overall_status = (
        "ok"
        if database_health["status"] == "connected"
        else "degraded"
    )

    return {
        "status": overall_status,
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "database": database_health,
        "engine_ready": True,
        "skus_in_data": int(
            promo_engine.panel_df["SKU"].nunique()
        ),
        "data_years": _train_yr_str(),
        "n_years": len(training_years),
    }