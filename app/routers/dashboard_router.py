"""Dashboard API routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.schemas.dashboard import DashboardResponse
from app.services import dashboard_service


router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
)


@router.get(
    "",
    response_model=DashboardResponse,
    summary="Get user dashboard",
)
def get_dashboard(
    user_id: str = Query(
        ...,
        min_length=1,
        description=(
            "User ID used to fetch projects and scenarios. "
            "This will later come from the JWT token."
        ),
    ),
    database_session: Session = Depends(get_db),
) -> DashboardResponse:
    """Return all active projects and scenarios for a user."""

    return dashboard_service.get_dashboard(
        database_session=database_session,
        user_id=user_id,
    )