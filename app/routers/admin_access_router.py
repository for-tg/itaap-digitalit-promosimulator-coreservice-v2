"""Admin region access API routes."""

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.dependencies.jwt_auth import RoleChecker
from app.schemas.access import (
    AccessRequestListResponse,
    AccessRequestResponse,
    ReviewAccessRequest,
    UserRegionAccessListResponse,
    UserRegionAccessResponse,
)
from app.services import access_service


router = APIRouter(
    prefix="/api/admin",
    tags=["Admin Region Access"],
    # dependencies=[
    #     Depends(RoleChecker("ADMIN")),
    # ],
)


def _get_admin_user_id(
    request: Request,
) -> str:
    """Return the authenticated admin user ID."""

    return getattr(
        request.state,
        "user_id",
        getattr(
            request.state,
            "client_id",
            "local-admin",
        ),
    )


@router.get(
    "/access-requests/pending",
    response_model=AccessRequestListResponse,
    summary="List pending access requests",
)
def list_pending_requests(
    database_session: Session = Depends(get_db),
) -> AccessRequestListResponse:
    """Return all pending region access requests."""

    return access_service.list_pending_requests(
        database_session=database_session,
    )


@router.post(
    "/access-requests/{request_id}/approve",
    response_model=AccessRequestResponse,
    summary="Approve access request",
)
def approve_access_request(
    request_id: str,
    review_data: ReviewAccessRequest,
    request: Request,
    database_session: Session = Depends(get_db),
) -> AccessRequestResponse:
    """Approve a pending region access request."""

    return access_service.approve_access_request(
        database_session=database_session,
        request_id=request_id,
        admin_user_id=_get_admin_user_id(request),
        review_data=review_data,
    )


@router.post(
    "/access-requests/{request_id}/reject",
    response_model=AccessRequestResponse,
    summary="Reject access request",
)
def reject_access_request(
    request_id: str,
    review_data: ReviewAccessRequest,
    request: Request,
    database_session: Session = Depends(get_db),
) -> AccessRequestResponse:
    """Reject a pending region access request."""

    return access_service.reject_access_request(
        database_session=database_session,
        request_id=request_id,
        admin_user_id=_get_admin_user_id(request),
        review_data=review_data,
    )


@router.get(
    "/users/active",
    response_model=UserRegionAccessListResponse,
    summary="List active user region access",
)
def list_active_users(
    database_session: Session = Depends(get_db),
) -> UserRegionAccessListResponse:
    """Return all currently active user-region access."""

    return access_service.list_active_users(
        database_session=database_session,
    )


@router.get(
    "/users/deleted",
    response_model=UserRegionAccessListResponse,
    summary="List revoked user region access",
)
def list_deleted_users(
    database_session: Session = Depends(get_db),
) -> UserRegionAccessListResponse:
    """Return revoked/deleted region access."""

    return access_service.list_deleted_users(
        database_session=database_session,
    )


@router.delete(
    "/users/{user_id}/regions/{region_id}",
    response_model=UserRegionAccessResponse,
    summary="Revoke user region access",
)
def revoke_region_access(
    user_id: str,
    region_id: str,
    request: Request,
    database_session: Session = Depends(get_db),
) -> UserRegionAccessResponse:
    """Revoke one region from a user."""

    return access_service.revoke_region_access(
        database_session=database_session,
        user_id=user_id,
        region_id=region_id,
        admin_user_id=_get_admin_user_id(request),
    )