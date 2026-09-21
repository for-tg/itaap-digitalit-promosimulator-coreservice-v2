from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.routers.admin_access_router import (
    _get_admin_user_id,
    approve_access_request,
    list_active_users,
    list_deleted_users,
    list_pending_requests,
    reject_access_request,
    revoke_region_access,
)


# ==========================================================
# _get_admin_user_id
# ==========================================================

def test_get_admin_user_id_from_user_id():
    request = MagicMock()
    request.state = SimpleNamespace(
        user_id="admin123",
    )

    assert (
        _get_admin_user_id(request)
        == "admin123"
    )


def test_get_admin_user_id_from_client_id():
    request = MagicMock()
    request.state = SimpleNamespace(
        client_id="client123",
    )

    assert (
        _get_admin_user_id(request)
        == "client123"
    )


def test_get_admin_user_id_default():
    request = MagicMock()
    request.state = SimpleNamespace()

    assert (
        _get_admin_user_id(request)
        == "local-admin"
    )


# ==========================================================
# list_pending_requests
# ==========================================================

@patch(
    "app.routers.admin_access_router.access_service.list_pending_requests"
)
def test_list_pending_requests(
    mock_list_pending_requests,
):
    db_session = MagicMock()

    expected = MagicMock()

    mock_list_pending_requests.return_value = expected

    result = list_pending_requests(
        database_session=db_session,
    )

    assert result == expected

    mock_list_pending_requests.assert_called_once_with(
        database_session=db_session,
    )


# ==========================================================
# approve_access_request
# ==========================================================

@patch(
    "app.routers.admin_access_router.access_service.approve_access_request"
)
def test_approve_access_request(
    mock_approve_access_request,
):
    db_session = MagicMock()

    request = MagicMock()
    request.state = SimpleNamespace(
        user_id="admin123",
    )

    review_data = MagicMock()

    expected = MagicMock()

    mock_approve_access_request.return_value = expected

    result = approve_access_request(
        request_id="req123",
        review_data=review_data,
        request=request,
        database_session=db_session,
    )

    assert result == expected

    mock_approve_access_request.assert_called_once_with(
        database_session=db_session,
        request_id="req123",
        admin_user_id="admin123",
        review_data=review_data,
    )


# ==========================================================
# reject_access_request
# ==========================================================

@patch(
    "app.routers.admin_access_router.access_service.reject_access_request"
)
def test_reject_access_request(
    mock_reject_access_request,
):
    db_session = MagicMock()

    request = MagicMock()
    request.state = SimpleNamespace(
        user_id="admin123",
    )

    review_data = MagicMock()

    expected = MagicMock()

    mock_reject_access_request.return_value = expected

    result = reject_access_request(
        request_id="req123",
        review_data=review_data,
        request=request,
        database_session=db_session,
    )

    assert result == expected

    mock_reject_access_request.assert_called_once_with(
        database_session=db_session,
        request_id="req123",
        admin_user_id="admin123",
        review_data=review_data,
    )


# ==========================================================
# list_active_users
# ==========================================================

@patch(
    "app.routers.admin_access_router.access_service.list_active_users"
)
def test_list_active_users(
    mock_list_active_users,
):
    db_session = MagicMock()

    expected = MagicMock()

    mock_list_active_users.return_value = expected

    result = list_active_users(
        database_session=db_session,
    )

    assert result == expected

    mock_list_active_users.assert_called_once_with(
        database_session=db_session,
    )


# ==========================================================
# list_deleted_users
# ==========================================================

@patch(
    "app.routers.admin_access_router.access_service.list_deleted_users"
)
def test_list_deleted_users(
    mock_list_deleted_users,
):
    db_session = MagicMock()

    expected = MagicMock()

    mock_list_deleted_users.return_value = expected

    result = list_deleted_users(
        database_session=db_session,
    )

    assert result == expected

    mock_list_deleted_users.assert_called_once_with(
        database_session=db_session,
    )


# ==========================================================
# revoke_region_access
# ==========================================================

@patch(
    "app.routers.admin_access_router.access_service.revoke_region_access"
)
def test_revoke_region_access(
    mock_revoke_region_access,
):
    db_session = MagicMock()

    request = MagicMock()
    request.state = SimpleNamespace(
        user_id="admin123",
    )

    expected = MagicMock()

    mock_revoke_region_access.return_value = expected

    result = revoke_region_access(
        user_id="user1",
        region_id="region1",
        request=request,
        database_session=db_session,
    )

    assert result == expected

    mock_revoke_region_access.assert_called_once_with(
        database_session=db_session,
        user_id="user1",
        region_id="region1",
        admin_user_id="admin123",
    )