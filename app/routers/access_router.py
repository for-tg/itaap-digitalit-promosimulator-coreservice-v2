"""User region access API routes."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.schemas.access import (
    AccessRequestListResponse,
    AccessRequestResponse,
    CreateAccessRequest,
    MyAccessResponse,
    RegionResponse,
)
from app.services import access_service


router = APIRouter(
    prefix="/api",
    tags=["Region Access"],
)


def _get_current_user_id(request: Request) -> str:
    """Return the authenticated user ID."""

    return getattr(
        request.state,
        "user_id",
        getattr(
            request.state,
            "client_id",
            "local-user",
        ),
    )


def _get_current_user_name(
    request: Request,
) -> str | None:
    """Return the authenticated user name when available."""

    return getattr(
        request.state,
        "user_name",
        None,
    )


def _get_current_user_email(
    request: Request,
) -> str | None:
    """Return the authenticated user email when available."""

    return getattr(
        request.state,
        "user_email",
        None,
    )


@router.get(
    "/regions",
    response_model=list[RegionResponse],
    summary="List available regions",
)
def list_regions(
    database_session: Session = Depends(get_db),
) -> list[RegionResponse]:
    """Return all active regions available for access requests."""

    return access_service.list_regions(
        database_session=database_session,
    )


@router.post(
    "/access-requests",
    response_model=AccessRequestResponse,
    status_code=201,
    summary="Request region access",
)
def create_access_request(
    request_data: CreateAccessRequest,
    request: Request,
    database_session: Session = Depends(get_db),
) -> AccessRequestResponse:
    """Create a new region access request."""

    return access_service.create_access_request(
        database_session=database_session,
        user_id=_get_current_user_id(request),
        user_name=_get_current_user_name(request),
        user_email=_get_current_user_email(request),
        request_data=request_data,
    )


@router.get(
    "/access-requests/me",
    response_model=AccessRequestListResponse,
    summary="Get my access requests",
)
def get_my_requests(
    request: Request,
    database_session: Session = Depends(get_db),
) -> AccessRequestListResponse:
    """Return access request history for the current user."""

    return access_service.get_my_requests(
        database_session=database_session,
        user_id=_get_current_user_id(request),
    )


@router.get(
    "/access/me",
    response_model=MyAccessResponse,
    summary="Get my current region access",
)
def get_my_access(
    request: Request,
    database_session: Session = Depends(get_db),
) -> MyAccessResponse:
    """Return current active regions and pending request."""

    return access_service.get_my_access(
        database_session=database_session,
        user_id=_get_current_user_id(request),
    )