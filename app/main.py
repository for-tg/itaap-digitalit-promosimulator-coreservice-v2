"""
FastAPI application main entry point.

Initializes authentication, logging, database tables, exception handlers,
middleware, API routes, telemetry, and the ML model during startup.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from itaap_python_utils.exceptions.base import ServiceException
from itaap_python_utils.logging.manager import LogManager

from app.config.database import Base, engine
from app.config.settings import settings

from app.database.models.access_request import (
    AccessRequest,
    AccessRequestRegion,
)  # noqa: F401
from app.database.models.optimization_result import OptimizationResult  # noqa: F401
from app.database.models.project import Project  # noqa: F401
from app.database.models.region import Region  # noqa: F401
from app.database.models.scenario import Scenario  # noqa: F401
from app.database.models.scenario_config import ScenarioConfig  # noqa: F401
from app.database.models.sku import SKU  # noqa: F401
from app.database.models.user_region_access import UserRegionAccess  # noqa: F401

from app.dependencies.jwt_auth import TokenValidator
from app.exceptions.handler import (
    handle_generic_exception,
    handle_service_exception,
)
from app.middleware.trace_middleware import trace_middleware

from app.routers import (
    access_router,
    admin_access_router,
    dashboard_router,
    health_router,
    historical_data_router,
    optimization_result_router,
    project_router,
    sample,
    scenario_config_router,
    scenario_optimization_router,
    scenario_router,
    simulation_router,
    sku_master_router,
    skus_router,
)

from app.services.model_loader import load_model
from app.utils.network_check import run_postgres_telnet_check


try:
    from app.telemetry.config import setup_telemetry
except ImportError:
    setup_telemetry = None


# Initialize application logging before startup begins.
LogManager.init_logger(
    app_name=settings.APP_NAME,
    app_version=settings.APP_VERSION,
    environment=settings.APP_ENV,
    log_level=settings.LOG_LEVEL_APP,
)

logger = LogManager.get_logger()



@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Initialize application resources during startup."""

    logger.info("Initializing promo simulator application")

    logger.info(
        "Application startup configuration. "
        "env=%s host=%s port=%s database=%s user=%s",
        settings.APP_ENV,
        settings.AWS_DB_HOST,
        settings.AWS_DB_PORT,
        settings.AWS_DB_NAME,
        settings.AWS_DB_USER,
    )

    # Temporary DEV PostgreSQL network connectivity test.
    if settings.APP_ENV.lower() != "local":
        logger.info(
            "Starting PostgreSQL connectivity validation."
        )

        run_postgres_telnet_check()

        logger.info(
            "PostgreSQL connectivity validation completed."
        )

    logger.info(
        "About to initialize database tables."
    )

    try:
        logger.info(
            "Attempting Base.metadata.create_all()"
        )

        Base.metadata.create_all(bind=engine)

        logger.info(
            "Base.metadata.create_all() completed successfully."
        )

    except Exception as exc:
        logger.exception(
            "Database initialization failed. "
            "host=%s port=%s database=%s error=%s",
            settings.AWS_DB_HOST,
            settings.AWS_DB_PORT,
            settings.AWS_DB_NAME,
            str(exc),
        )

        raise

    logger.info("Database tables initialized successfully")

    logger.info("Starting model load.")

    try:
        load_model()

        logger.info(
            "Model loaded successfully."
        )

    except Exception:
        logger.exception(
            "Model loading failed."
        )
        raise

    logger.info(
        "Promo simulator application initialized successfully"
    )

    yield

    logger.info(
        "Promo simulator application shutting down"
    )

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if (
    settings.SEND_TELEMETRY_DATA.lower() == "true"
    and setup_telemetry is not None
):
    setup_telemetry(app)

app.middleware("http")(trace_middleware)

app.add_exception_handler(
    ServiceException,
    handle_service_exception,
)

app.add_exception_handler(
    Exception,
    handle_generic_exception,
)

validator = TokenValidator()

api_prefix = f"/{settings.APP_NAME}"


# ------------------------------------------------------------------
# Public endpoints
# ------------------------------------------------------------------

app.include_router(
    health_router.router,
    prefix=api_prefix,
)


# ------------------------------------------------------------------
# Protected application endpoints
# ------------------------------------------------------------------

app.include_router(
    skus_router.router,
    prefix=api_prefix,
    dependencies=[Depends(validator)],
)

app.include_router(
    simulation_router.router,
    prefix=api_prefix,
    dependencies=[Depends(validator)],
)

app.include_router(
    historical_data_router.router,
    prefix=api_prefix,
    dependencies=[Depends(validator)],
)

app.include_router(
    project_router.router,
    prefix=api_prefix,
    dependencies=[Depends(validator)],
)

app.include_router(
    sample.router,
    prefix=api_prefix,
    dependencies=[Depends(validator)],
)

app.include_router(
    scenario_router.router,
    prefix=api_prefix,
    dependencies=[Depends(validator)],
)

app.include_router(
    dashboard_router.router,
    prefix=api_prefix,
    dependencies=[Depends(validator)],
)

app.include_router(
    scenario_config_router.router,
    prefix=api_prefix,
    dependencies=[Depends(validator)],
)

app.include_router(
    optimization_result_router.router,
    prefix=api_prefix,
    dependencies=[Depends(validator)],
)

app.include_router(
    scenario_optimization_router.router,
    prefix=api_prefix,
    dependencies=[Depends(validator)],
)

app.include_router(
    sku_master_router.router,
    prefix=api_prefix,
    dependencies=[Depends(validator)],
)


# ------------------------------------------------------------------
# Region access APIs
# ------------------------------------------------------------------

# Normal authenticated user APIs.
app.include_router(
    access_router.router,
    prefix=api_prefix,
    dependencies=[Depends(validator)],
)

# Admin APIs.
# The ADMIN role check is already applied inside admin_access_router.
app.include_router(
    admin_access_router.router,
    prefix=api_prefix,
    dependencies=[Depends(validator)],
)


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting server")

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=9000,
        reload=False,
        access_log=True,
        log_level="info",
    )

    # dummy trigger 10