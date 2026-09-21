"""Database operations for optimization results."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.optimization_result import OptimizationResult
from app.schemas.optimization_result import OptimizationResultUpsert


def get_optimization_result(
    database_session: Session,
    scenario_id: str,
) -> OptimizationResult | None:
    """Return the optimization result for a scenario."""

    statement = select(OptimizationResult).where(
        OptimizationResult.scenario_id == scenario_id,
    )

    return database_session.scalar(statement)


def upsert_optimization_result(
    database_session: Session,
    scenario_id: str,
    result_data: OptimizationResultUpsert,
) -> OptimizationResult:
    """Create or update an optimization result."""

    optimization_result = get_optimization_result(
        database_session=database_session,
        scenario_id=scenario_id,
    )

    if optimization_result is None:
        optimization_result = OptimizationResult(
            scenario_id=scenario_id,
            result_json=result_data.result_json,
        )
    else:
        optimization_result.result_json = result_data.result_json

    database_session.add(optimization_result)
    database_session.commit()
    database_session.refresh(optimization_result)

    return optimization_result


def delete_optimization_result(
    database_session: Session,
    optimization_result: OptimizationResult,
) -> None:
    """Delete an optimization result."""

    database_session.delete(optimization_result)
    database_session.commit()