"""Scenario optimization workflow service."""

import logging
from typing import Any

from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.database.models.scenario import ScenarioStatus
from app.database.repositories import (
    optimization_result_repository,
    scenario_config_repository,
    scenario_repository,
)
from app.engine import promo_engine
from app.routers.simulation_router import run_plan, run_retro
from app.schemas.optimization_result import OptimizationResultUpsert
from app.schemas.requests import PlanRequest, RetroRequest
from app.schemas.scenario_config import AnalysisType


logger = logging.getLogger(__name__)


def optimize_scenario(
    database_session: Session,
    scenario_id: str,
) -> dict[str, Any]:
    """Run optimization using the scenario's saved configuration."""

    cleaned_scenario_id = scenario_id.strip()

    if not cleaned_scenario_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scenario_id must not be empty.",
        )

    scenario = scenario_repository.get_scenario_by_id(
        database_session=database_session,
        scenario_id=cleaned_scenario_id,
    )

    if scenario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found.",
        )

    scenario_config = (
        scenario_config_repository.get_config_by_scenario_id(
            database_session=database_session,
            scenario_id=cleaned_scenario_id,
        )
    )

    if scenario_config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Scenario configuration not found. "
                "Save the configuration before running optimization."
            ),
        )

    if not promo_engine.is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Promotion engine is still loading.",
        )

    scenario_repository.update_scenario_status(
        database_session=database_session,
        scenario=scenario,
        scenario_status=ScenarioStatus.RUNNING.value,
    )

    try:
        optimization_result = _execute_optimization(
            scenario_config=scenario_config,
        )

        serializable_result = jsonable_encoder(
            optimization_result
        )

        stored_result = (
            optimization_result_repository.upsert_optimization_result(
                database_session=database_session,
                scenario_id=cleaned_scenario_id,
                result_data=OptimizationResultUpsert(
                    result_json=serializable_result,
                ),
            )
        )

        scenario_repository.update_scenario_status(
            database_session=database_session,
            scenario=scenario,
            scenario_status=ScenarioStatus.COMPLETED.value,
        )

        return {
            "scenario_id": cleaned_scenario_id,
            "status": ScenarioStatus.COMPLETED.value,
            "result": stored_result.result_json,
            "created_at": stored_result.created_at,
            "updated_at": stored_result.updated_at,
        }

    except HTTPException:
        _mark_scenario_failed(
            database_session=database_session,
            scenario=scenario,
        )
        raise

    except Exception as exc:
        _mark_scenario_failed(
            database_session=database_session,
            scenario=scenario,
        )

        logger.exception(
            "Unexpected error while optimizing scenario %s.",
            cleaned_scenario_id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to complete scenario optimization.",
        ) from exc


def _execute_optimization(
    scenario_config: Any,
) -> dict[str, Any]:
    """Execute retro or plan optimization from stored configuration."""

    analysis_type = str(
        scenario_config.analysis_type
    ).lower()

    if analysis_type == AnalysisType.RETRO.value:
        request = RetroRequest(
            skus=scenario_config.selected_skus,
            year=scenario_config.year,
            period=scenario_config.period,
            objective=scenario_config.objective,
            max_discount=scenario_config.max_discount,
            budget_multiplier=scenario_config.budget_multiplier,
            ref_year=scenario_config.reference_year,
            unconstrained=scenario_config.unconstrained,
            alpha=scenario_config.alpha,
            margin_floor=scenario_config.margin_floor,
            allocation_mode=scenario_config.allocation_mode,
            q_splits=scenario_config.quarterly_splits,
            economics=scenario_config.economics,
        )

        return run_retro(request)

    if analysis_type == AnalysisType.PLAN.value:
        request = PlanRequest(
            skus=scenario_config.selected_skus,
            plan_year=scenario_config.plan_year,
            base_year=scenario_config.base_year,
            use_trend=scenario_config.use_trend,
            objective=scenario_config.objective,
            max_discount=scenario_config.max_discount,
            budget_multiplier=scenario_config.budget_multiplier,
            ref_year=scenario_config.reference_year,
            q_splits=scenario_config.quarterly_splits,
            unconstrained=scenario_config.unconstrained,
            alpha=scenario_config.alpha,
            margin_floor=scenario_config.margin_floor,
            economics=scenario_config.economics,

        )

        return run_plan(request)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            "Unsupported analysis type. "
            "Supported values are 'retro' and 'plan'."
        ),
    )


def _mark_scenario_failed(
    database_session: Session,
    scenario: Any,
) -> None:
    """Safely mark a scenario as failed."""

    try:
        scenario_repository.update_scenario_status(
            database_session=database_session,
            scenario=scenario,
            scenario_status=ScenarioStatus.FAILED.value,
        )

    except Exception:
        database_session.rollback()

        logger.exception(
            "Failed to update scenario %s status to FAILED.",
            scenario.scenario_id,
        )