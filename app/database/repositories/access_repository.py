"""Database operations for region access requests and user access."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.models.access_request import (
    AccessRequest,
    AccessRequestRegion,
    AccessRequestStatus,
)
from app.database.models.region import Region
from app.database.models.user_region_access import UserRegionAccess
from app.utils.encryption import encrypt_email


def utc_now() -> datetime:
    """Return the current UTC datetime."""

    return datetime.now(timezone.utc)


def list_active_regions(
    database_session: Session,
) -> list[Region]:
    """Return all active regions."""

    statement = (
        select(Region)
        .where(
            Region.is_active.is_(True),
        )
        .order_by(
            Region.region_name.asc(),
        )
    )

    return list(
        database_session.scalars(statement).all()
    )


def get_regions_by_ids(
    database_session: Session,
    region_ids: list[str],
) -> list[Region]:
    """Return active regions matching the supplied IDs."""

    if not region_ids:
        return []

    statement = select(Region).where(
        Region.region_id.in_(region_ids),
        Region.is_active.is_(True),
    )

    return list(
        database_session.scalars(statement).all()
    )


def get_pending_request_for_user(
    database_session: Session,
    user_id: str,
) -> AccessRequest | None:
    """Return the user's current pending request."""

    statement = (
        select(AccessRequest)
        .options(
            selectinload(AccessRequest.regions).selectinload(
                AccessRequestRegion.region
            )
        )
        .where(
            AccessRequest.user_id == user_id,
            AccessRequest.status == AccessRequestStatus.PENDING.value,
        )
        .order_by(
            AccessRequest.created_at.desc(),
        )
    )

    return database_session.scalar(statement)


def create_access_request(
    database_session: Session,
    user_id: str,
    user_name: str | None,
    user_email: str | None,
    regions: list[Region],
) -> AccessRequest:
    """Create one access request for one or more regions."""

    access_request = AccessRequest(
        user_id=user_id,
        requested_by_name=user_name,
        requested_by_email=(
            encrypt_email(user_email)
            if user_email
            else None
        ),
        status=AccessRequestStatus.PENDING.value,
    )


    for region in regions:
        access_request.regions.append(
            AccessRequestRegion(
                region_id=region.region_id,
            )
        )

    database_session.add(access_request)
    database_session.commit()

    return get_access_request_by_id(
        database_session=database_session,
        request_id=access_request.request_id,
    )


def get_access_request_by_id(
    database_session: Session,
    request_id: str,
) -> AccessRequest | None:
    """Return one access request including its regions."""

    statement = (
        select(AccessRequest)
        .options(
            selectinload(AccessRequest.regions).selectinload(
                AccessRequestRegion.region
            )
        )
        .where(
            AccessRequest.request_id == request_id,
        )
    )

    return database_session.scalar(statement)


def list_access_requests_for_user(
    database_session: Session,
    user_id: str,
) -> list[AccessRequest]:
    """Return all access requests created by a user."""

    statement = (
        select(AccessRequest)
        .options(
            selectinload(AccessRequest.regions).selectinload(
                AccessRequestRegion.region
            )
        )
        .where(
            AccessRequest.user_id == user_id,
        )
        .order_by(
            AccessRequest.created_at.desc(),
        )
    )

    return list(
        database_session.scalars(statement).all()
    )

def list_pending_requests(
    database_session: Session,
) -> list[AccessRequest]:
    """Return pending requests for admin review."""

    statement = (
        select(AccessRequest)
        .options(
            selectinload(AccessRequest.regions).selectinload(
                AccessRequestRegion.region
            )
        )
        .where(
            AccessRequest.status == AccessRequestStatus.PENDING.value,
        )
        .order_by(
            AccessRequest.created_at.asc(),
        )
    )

    return list(
        database_session.scalars(statement).all()
    )

   

def approve_access_request(
    database_session: Session,
    access_request: AccessRequest,
    admin_user_id: str,
    review_comment: str | None = None,
) -> AccessRequest:
    """Approve a pending access request."""

    access_request.status = AccessRequestStatus.APPROVED.value
    access_request.reviewed_by = admin_user_id
    access_request.review_comment = review_comment
    access_request.reviewed_at = utc_now()

    database_session.add(access_request)
    database_session.commit()
    database_session.refresh(access_request)

    return access_request


def reject_access_request(
    database_session: Session,
    access_request: AccessRequest,
    admin_user_id: str,
    review_comment: str | None = None,
) -> AccessRequest:
    """Reject a pending access request."""

    access_request.status = AccessRequestStatus.REJECTED.value
    access_request.reviewed_by = admin_user_id
    access_request.review_comment = review_comment
    access_request.reviewed_at = utc_now()

    database_session.add(access_request)
    database_session.commit()
    database_session.refresh(access_request)

    return access_request


def get_user_region_access(
    database_session: Session,
    user_id: str,
    region_id: str,
) -> UserRegionAccess | None:
    """Return one user-region access record."""

    statement = select(UserRegionAccess).where(
        UserRegionAccess.user_id == user_id,
        UserRegionAccess.region_id == region_id,
    )

    return database_session.scalar(statement)


def grant_region_access(
    database_session: Session,
    user_id: str,
    region_id: str,
    admin_user_id: str,
) -> UserRegionAccess:
    """Grant or reactivate one region for a user."""

    access = get_user_region_access(
        database_session=database_session,
        user_id=user_id,
        region_id=region_id,
    )

    if access is None:
        access = UserRegionAccess(
            user_id=user_id,
            region_id=region_id,
            is_active=True,
            granted_by=admin_user_id,
            granted_at=utc_now(),
        )

    else:
        access.is_active = True
        access.granted_by = admin_user_id
        access.granted_at = utc_now()
        access.revoked_by = None
        access.revoked_at = None

    database_session.add(access)

    return access


def commit_access_changes(
    database_session: Session,
) -> None:
    """Commit access-related database changes."""

    database_session.commit()


def list_active_user_access(
    database_session: Session,
) -> list[UserRegionAccess]:
    """Return all active user-region access records."""

    statement = (
        select(UserRegionAccess)
        .options(
            selectinload(UserRegionAccess.region)
        )
        .where(
            UserRegionAccess.is_active.is_(True),
        )
        .order_by(
            UserRegionAccess.user_id.asc(),
            UserRegionAccess.created_at.asc(),
        )
    )

    return list(
        database_session.scalars(statement).all()
    )


def list_revoked_user_access(
    database_session: Session,
) -> list[UserRegionAccess]:
    """Return all revoked user-region access records."""

    statement = (
        select(UserRegionAccess)
        .options(
            selectinload(UserRegionAccess.region)
        )
        .where(
            UserRegionAccess.is_active.is_(False),
        )
        .order_by(
            UserRegionAccess.updated_at.desc(),
        )
    )

    return list(
        database_session.scalars(statement).all()
    )


def list_user_active_regions(
    database_session: Session,
    user_id: str,
) -> list[UserRegionAccess]:
    """Return active regions granted to one user."""

    statement = (
        select(UserRegionAccess)
        .options(
            selectinload(UserRegionAccess.region)
        )
        .where(
            UserRegionAccess.user_id == user_id,
            UserRegionAccess.is_active.is_(True),
        )
        .order_by(
            UserRegionAccess.created_at.asc(),
        )
    )

    return list(
        database_session.scalars(statement).all()
    )


def revoke_region_access(
    database_session: Session,
    access: UserRegionAccess,
    admin_user_id: str,
) -> UserRegionAccess:
    """Revoke one region from a user."""

    access.is_active = False
    access.revoked_by = admin_user_id
    access.revoked_at = utc_now()

    database_session.add(access)
    database_session.commit()
    database_session.refresh(access)

    return access