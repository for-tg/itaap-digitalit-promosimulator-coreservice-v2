"""Optimization result API routes."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.schemas.optimization_result import (
    OptimizationResultResponse,
    OptimizationResultUpsert,
)
from app.services import optimization_result_service


router = APIRouter(
    prefix="/api/scenarios",
    tags=["Optimization Result"],
)


@router.get(
    "/{scenario_id}/optimization-result",
    response_model=OptimizationResultResponse,
    summary="Get optimization result",
)
def get_optimization_result(
    scenario_id: str,
    database_session: Session = Depends(get_db),
) -> OptimizationResultResponse:
    """Return the optimization result for a scenario."""

    return optimization_result_service.get_optimization_result(
        database_session=database_session,
        scenario_id=scenario_id,
    )


@router.put(
    "/{scenario_id}/optimization-result",
    response_model=OptimizationResultResponse,
    summary="Create or update optimization result",
)
def upsert_optimization_result(
    scenario_id: str,
    result_data: OptimizationResultUpsert,
    database_session: Session = Depends(get_db),
) -> OptimizationResultResponse:
    """Create or update the optimization result."""

    return optimization_result_service.upsert_optimization_result(
        database_session=database_session,
        scenario_id=scenario_id,
        result_data=result_data,
    )


@router.delete(
    "/{scenario_id}/optimization-result",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete optimization result",
)
def delete_optimization_result(
    scenario_id: str,
    database_session: Session = Depends(get_db),
) -> Response:
    """Delete an optimization result."""

    optimization_result_service.delete_optimization_result(
        database_session=database_session,
        scenario_id=scenario_id,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )