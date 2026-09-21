from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.database.repositories.access_repository import (
    approve_access_request,
    commit_access_changes,
    create_access_request,
    get_access_request_by_id,
    get_pending_request_for_user,
    get_regions_by_ids,
    get_user_region_access,
    grant_region_access,
    list_access_requests_for_user,
    list_active_regions,
    list_active_user_access,
    list_pending_requests,
    list_revoked_user_access,
    list_user_active_regions,
    reject_access_request,
    revoke_region_access,
    utc_now,
)


# ==========================================================
# utc_now
# ==========================================================

def test_utc_now():
    result = utc_now()

    assert isinstance(result, datetime)
    assert result.tzinfo == timezone.utc


# ==========================================================
# list_active_regions
# ==========================================================

def test_list_active_regions():
    session = MagicMock()

    region1 = MagicMock()
    region2 = MagicMock()

    session.scalars.return_value.all.return_value = [
        region1,
        region2,
    ]

    result = list_active_regions(session)

    assert result == [region1, region2]


# ==========================================================
# get_regions_by_ids
# ==========================================================

def test_get_regions_by_ids_empty():
    session = MagicMock()

    result = get_regions_by_ids(
        session,
        [],
    )

    assert result == []


def test_get_regions_by_ids():
    session = MagicMock()

    region = MagicMock()

    session.scalars.return_value.all.return_value = [
        region
    ]

    result = get_regions_by_ids(
        session,
        ["1"],
    )

    assert result == [region]


# ==========================================================
# get_pending_request_for_user
# ==========================================================

def test_get_pending_request_for_user():
    session = MagicMock()

    request = MagicMock()

    session.scalar.return_value = request

    result = get_pending_request_for_user(
        session,
        "user1",
    )

    assert result == request


# ==========================================================
# create_access_request
# ==========================================================

@patch(
    "app.database.repositories.access_repository.get_access_request_by_id"
)
@patch(
    "app.database.repositories.access_repository.encrypt_email"
)
@patch(
    "app.database.repositories.access_repository.AccessRequestRegion"
)
@patch(
    "app.database.repositories.access_repository.AccessRequest"
)
def test_create_access_request_with_email(
    mock_access_request,
    mock_region_model,
    mock_encrypt,
    mock_get_by_id,
):
    session = MagicMock()

    mock_encrypt.return_value = "encrypted"

    access_request = MagicMock()
    access_request.request_id = "req1"
    access_request.regions = []

    mock_access_request.return_value = access_request

    region = MagicMock()
    region.region_id = "r1"

    expected = MagicMock()

    mock_get_by_id.return_value = expected

    result = create_access_request(
        session,
        "user1",
        "John",
        "john@test.com",
        [region],
    )

    assert result == expected

    mock_encrypt.assert_called_once_with(
        "john@test.com"
    )

    session.add.assert_called_once()
    session.commit.assert_called_once()


@patch(
    "app.database.repositories.access_repository.get_access_request_by_id"
)
@patch(
    "app.database.repositories.access_repository.AccessRequest"
)
def test_create_access_request_without_email(
    mock_access_request,
    mock_get_by_id,
):
    session = MagicMock()

    access_request = MagicMock()
    access_request.request_id = "req1"
    access_request.regions = []

    mock_access_request.return_value = access_request

    mock_get_by_id.return_value = access_request

    result = create_access_request(
        session,
        "user1",
        None,
        None,
        [],
    )

    assert result == access_request


# ==========================================================
# get_access_request_by_id
# ==========================================================

def test_get_access_request_by_id():
    session = MagicMock()

    obj = MagicMock()

    session.scalar.return_value = obj

    result = get_access_request_by_id(
        session,
        "req1",
    )

    assert result == obj


# ==========================================================
# list_access_requests_for_user
# ==========================================================

def test_list_access_requests_for_user():
    session = MagicMock()

    session.scalars.return_value.all.return_value = [
        1,
        2,
    ]

    result = list_access_requests_for_user(
        session,
        "user1",
    )

    assert result == [1, 2]


# ==========================================================
# list_pending_requests
# ==========================================================

def test_list_pending_requests():
    session = MagicMock()

    session.scalars.return_value.all.return_value = [
        1,
        2,
    ]

    result = list_pending_requests(
        session
    )

    assert result == [1, 2]


# ==========================================================
# approve_access_request
# ==========================================================

@patch(
    "app.database.repositories.access_repository.utc_now"
)
def test_approve_access_request(
    mock_utc_now,
):
    session = MagicMock()

    request = MagicMock()

    now = datetime.now(timezone.utc)

    mock_utc_now.return_value = now

    result = approve_access_request(
        session,
        request,
        "admin",
        "approved",
    )

    assert result == request
    assert request.reviewed_by == "admin"
    assert request.review_comment == "approved"

    session.add.assert_called_once_with(
        request
    )
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(
        request
    )


# ==========================================================
# reject_access_request
# ==========================================================

@patch(
    "app.database.repositories.access_repository.utc_now"
)
def test_reject_access_request(
    mock_utc_now,
):
    session = MagicMock()

    request = MagicMock()

    now = datetime.now(timezone.utc)

    mock_utc_now.return_value = now

    result = reject_access_request(
        session,
        request,
        "admin",
        "rejected",
    )

    assert result == request

    session.add.assert_called_once_with(
        request
    )
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(
        request
    )


# ==========================================================
# get_user_region_access
# ==========================================================

def test_get_user_region_access():
    session = MagicMock()

    access = MagicMock()

    session.scalar.return_value = access

    result = get_user_region_access(
        session,
        "user",
        "region",
    )

    assert result == access


# ==========================================================
# grant_region_access - create
# ==========================================================

@patch(
    "app.database.repositories.access_repository.utc_now"
)
@patch(
    "app.database.repositories.access_repository.UserRegionAccess"
)
@patch(
    "app.database.repositories.access_repository.get_user_region_access"
)
def test_grant_region_access_new(
    mock_get_access,
    mock_model,
    mock_utc_now,
):
    session = MagicMock()

    mock_get_access.return_value = None

    access_obj = MagicMock()

    mock_model.return_value = access_obj

    result = grant_region_access(
        session,
        "user",
        "region",
        "admin",
    )

    assert result == access_obj

    session.add.assert_called_once_with(
        access_obj
    )


# ==========================================================
# grant_region_access - reactivate
# ==========================================================

@patch(
    "app.database.repositories.access_repository.utc_now"
)
@patch(
    "app.database.repositories.access_repository.get_user_region_access"
)
def test_grant_region_access_existing(
    mock_get_access,
    mock_utc_now,
):
    session = MagicMock()

    access = MagicMock()

    mock_get_access.return_value = access

    result = grant_region_access(
        session,
        "user",
        "region",
        "admin",
    )

    assert result == access

    session.add.assert_called_once_with(
        access
    )


# ==========================================================
# commit_access_changes
# ==========================================================

def test_commit_access_changes():
    session = MagicMock()

    commit_access_changes(session)

    session.commit.assert_called_once()
    session.add.assert_not_called()
    session.refresh.assert_not_called()
    session.rollback.assert_not_called()