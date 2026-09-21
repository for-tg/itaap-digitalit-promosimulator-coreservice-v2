"""Business logic for region access management."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database.models.access_request import AccessRequestStatus
from app.database.repositories import access_repository
from app.schemas.access import (
    AccessRequestListResponse,
    AccessRequestRegionResponse,
    AccessRequestResponse,
    CreateAccessRequest,
    MyAccessResponse,
    RegionResponse,
    ReviewAccessRequest,
    UserRegionAccessListResponse,
    UserRegionAccessResponse,
)
from app.utils.encryption import decrypt_email


def list_regions(
    database_session: Session,
) -> list[RegionResponse]:
    """Return all active regions."""

    regions = access_repository.list_active_regions(
        database_session=database_session,
    )

    return [
        RegionResponse(
            region_id=region.region_id,
            region_code=region.region_code,
            region_name=region.region_name,
        )
        for region in regions
    ]


def create_access_request(
    database_session: Session,
    user_id: str,
    user_name: str | None,
    user_email: str | None,
    request_data: CreateAccessRequest,
) -> AccessRequestResponse:
    """Create a new region access request."""

    cleaned_user_id = user_id.strip()

    if not cleaned_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id must not be empty.",
        )

    pending_request = access_repository.get_pending_request_for_user(
        database_session=database_session,
        user_id=cleaned_user_id,
    )

    if pending_request is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "You already have a pending access request. "
                "Please wait until it is reviewed."
            ),
        )

    regions = access_repository.get_regions_by_ids(
        database_session=database_session,
        region_ids=request_data.region_ids,
    )

    if len(regions) != len(request_data.region_ids):
        found_region_ids = {
            region.region_id
            for region in regions
        }

        invalid_region_ids = [
            region_id
            for region_id in request_data.region_ids
            if region_id not in found_region_ids
        ]

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid or inactive region IDs: "
                + ", ".join(invalid_region_ids)
            ),
        )

    active_access = access_repository.list_user_active_regions(
        database_session=database_session,
        user_id=cleaned_user_id,
    )

    active_region_ids = {
        access.region_id
        for access in active_access
    }

    requested_region_ids = set(
        request_data.region_ids
    )

    if requested_region_ids.issubset(active_region_ids):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "You already have access to all selected regions."
            ),
        )

    request = access_repository.create_access_request(
        database_session=database_session,
        user_id=cleaned_user_id,
        user_name=user_name,
        user_email=user_email,
        regions=regions,
    )

    return _build_access_request_response(request)


def get_my_requests(
    database_session: Session,
    user_id: str,
) -> AccessRequestListResponse:
    """Return all access requests created by the current user."""

    requests = access_repository.list_access_requests_for_user(
        database_session=database_session,
        user_id=user_id,
    )

    responses = [
        _build_access_request_response(request)
        for request in requests
    ]

    return AccessRequestListResponse(
        total=len(responses),
        requests=responses,
    )


def get_my_access(
    database_session: Session,
    user_id: str,
) -> MyAccessResponse:
    """Return active regions and current pending request."""

    active_access = access_repository.list_user_active_regions(
        database_session=database_session,
        user_id=user_id,
    )

    pending_request = access_repository.get_pending_request_for_user(
        database_session=database_session,
        user_id=user_id,
    )

    return MyAccessResponse(
        user_id=user_id,
        active_regions=[
            _build_user_region_access_response(access)
            for access in active_access
        ],
        pending_request=(
            _build_access_request_response(
                pending_request
            )
            if pending_request is not None
            else None
        ),
    )


def list_pending_requests(
    database_session: Session,
) -> AccessRequestListResponse:
    """Return pending requests for admin review."""

    requests = access_repository.list_pending_requests(
        database_session=database_session,
    )

    responses = [
        _build_access_request_response(request)
        for request in requests
    ]

    return AccessRequestListResponse(
        total=len(responses),
        requests=responses,
    )


def approve_access_request(
    database_session: Session,
    request_id: str,
    admin_user_id: str,
    review_data: ReviewAccessRequest,
) -> AccessRequestResponse:
    """Approve a pending request and grant requested regions."""

    request = _get_pending_request(
        database_session=database_session,
        request_id=request_id,
    )

    for request_region in request.regions:
        access_repository.grant_region_access(
            database_session=database_session,
            user_id=request.user_id,
            region_id=request_region.region_id,
            admin_user_id=admin_user_id,
        )

    access_repository.approve_access_request(
        database_session=database_session,
        access_request=request,
        admin_user_id=admin_user_id,
        review_comment=review_data.comment,
    )

    access_repository.commit_access_changes(
        database_session=database_session,
    )

    updated_request = access_repository.get_access_request_by_id(
        database_session=database_session,
        request_id=request.request_id,
    )

    return _build_access_request_response(
        updated_request
    )


def reject_access_request(
    database_session: Session,
    request_id: str,
    admin_user_id: str,
    review_data: ReviewAccessRequest,
) -> AccessRequestResponse:
    """Reject a pending access request."""

    request = _get_pending_request(
        database_session=database_session,
        request_id=request_id,
    )

    rejected_request = access_repository.reject_access_request(
        database_session=database_session,
        access_request=request,
        admin_user_id=admin_user_id,
        review_comment=review_data.comment,
    )

    return _build_access_request_response(
        rejected_request
    )


def list_active_users(
    database_session: Session,
) -> UserRegionAccessListResponse:
    """Return all active user-region access records."""

    access_rows = access_repository.list_active_user_access(
        database_session=database_session,
    )

    responses = [
        _build_user_region_access_response(access)
        for access in access_rows
    ]

    return UserRegionAccessListResponse(
        total=len(responses),
        access=responses,
    )


def list_deleted_users(
    database_session: Session,
) -> UserRegionAccessListResponse:
    """Return revoked/deleted user-region access records."""

    access_rows = access_repository.list_revoked_user_access(
        database_session=database_session,
    )

    responses = [
        _build_user_region_access_response(access)
        for access in access_rows
    ]

    return UserRegionAccessListResponse(
        total=len(responses),
        access=responses,
    )


def revoke_region_access(
    database_session: Session,
    user_id: str,
    region_id: str,
    admin_user_id: str,
) -> UserRegionAccessResponse:
    """Revoke one region from a user."""

    access = access_repository.get_user_region_access(
        database_session=database_session,
        user_id=user_id,
        region_id=region_id,
    )

    if access is None or not access.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active region access not found.",
        )

    revoked_access = access_repository.revoke_region_access(
        database_session=database_session,
        access=access,
        admin_user_id=admin_user_id,
    )

    return _build_user_region_access_response(
        revoked_access
    )


def _get_pending_request(
    database_session: Session,
    request_id: str,
):
    """Return a pending request or raise an error."""

    request = access_repository.get_access_request_by_id(
        database_session=database_session,
        request_id=request_id.strip(),
    )

    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Access request not found.",
        )

    if request.status != AccessRequestStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Access request has already been reviewed.",
        )

    return request


def _build_access_request_response(
    request,
) -> AccessRequestResponse:
    """Convert an access request model to API response."""

    return AccessRequestResponse(
        request_id=request.request_id,
        user_id=request.user_id,
        requested_by_name=request.requested_by_name,
        requested_by_email=(
            decrypt_email(request.requested_by_email)
            if request.requested_by_email
            else None
        ),
        status=request.status,
        regions=[
            AccessRequestRegionResponse(
                region_id=item.region.region_id,
                region_code=item.region.region_code,
                region_name=item.region.region_name,
            )
            for item in request.regions
        ],
        reviewed_by=request.reviewed_by,
        review_comment=request.review_comment,
        created_at=request.created_at,
        reviewed_at=request.reviewed_at,
        updated_at=request.updated_at,
    )


def _build_user_region_access_response(
    access,
) -> UserRegionAccessResponse:
    """Convert user region access model to API response."""

    return UserRegionAccessResponse(
        access_id=access.access_id,
        user_id=access.user_id,
        region_id=access.region.region_id,
        region_code=access.region.region_code,
        region_name=access.region.region_name,
        is_active=access.is_active,
        granted_by=access.granted_by,
        granted_at=access.granted_at,
        revoked_by=access.revoked_by,
        revoked_at=access.revoked_at,
        created_at=access.created_at,
        updated_at=access.updated_at,
    )