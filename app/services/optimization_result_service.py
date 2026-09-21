"""Business logic for optimization result management."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database.repositories import (
    optimization_result_repository,
    scenario_repository,
)
from app.schemas.optimization_result import (
    OptimizationResultResponse,
    OptimizationResultUpsert,
)


def get_optimization_result(
    database_session: Session,
    scenario_id: str,
) -> OptimizationResultResponse:
    """Return the optimization result for a scenario."""

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

    optimization_result = (
        optimization_result_repository.get_optimization_result(
            database_session=database_session,
            scenario_id=cleaned_scenario_id,
        )
    )

    if optimization_result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Optimization result not found.",
        )

    return OptimizationResultResponse.model_validate(
        optimization_result
    )


def upsert_optimization_result(
    database_session: Session,
    scenario_id: str,
    result_data: OptimizationResultUpsert,
) -> OptimizationResultResponse:
    """Create or update an optimization result."""

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

    optimization_result = (
        optimization_result_repository.upsert_optimization_result(
            database_session=database_session,
            scenario_id=cleaned_scenario_id,
            result_data=result_data,
        )
    )

    return OptimizationResultResponse.model_validate(
        optimization_result
    )


def delete_optimization_result(
    database_session: Session,
    scenario_id: str,
) -> None:
    """Delete an optimization result."""

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

    optimization_result = (
        optimization_result_repository.get_optimization_result(
            database_session=database_session,
            scenario_id=cleaned_scenario_id,
        )
    )

    if optimization_result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Optimization result not found.",
        )

    optimization_result_repository.delete_optimization_result(
        database_session=database_session,
        optimization_result=optimization_result,
    )