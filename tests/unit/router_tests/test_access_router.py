from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.routers.access_router import (
    _get_current_user_email,
    _get_current_user_id,
    _get_current_user_name,
    create_access_request,
    get_my_access,
    get_my_requests,
    list_regions,
)


# ==========================================================
# Helper functions
# ==========================================================

def test_get_current_user_id_from_user_id():
    request = MagicMock()
    request.state = SimpleNamespace(
        user_id="user123"
    )

    assert (
        _get_current_user_id(request)
        == "user123"
    )


def test_get_current_user_id_from_client_id():
    request = MagicMock()
    request.state = SimpleNamespace(
        client_id="client123"
    )

    assert (
        _get_current_user_id(request)
        == "client123"
    )


def test_get_current_user_id_default():
    request = MagicMock()
    request.state = SimpleNamespace()

    assert (
        _get_current_user_id(request)
        == "local-user"
    )


def test_get_current_user_name():
    request = MagicMock()
    request.state = SimpleNamespace(
        user_name="John Doe"
    )

    assert (
        _get_current_user_name(request)
        == "John Doe"
    )


def test_get_current_user_name_none():
    request = MagicMock()
    request.state = SimpleNamespace()

    assert (
        _get_current_user_name(request)
        is None
    )


def test_get_current_user_email():
    request = MagicMock()
    request.state = SimpleNamespace(
        user_email="john@test.com"
    )

    assert (
        _get_current_user_email(request)
        == "john@test.com"
    )


def test_get_current_user_email_none():
    request = MagicMock()
    request.state = SimpleNamespace()

    assert (
        _get_current_user_email(request)
        is None
    )


# ==========================================================
# list_regions
# ==========================================================

@patch(
    "app.routers.access_router.access_service.list_regions"
)
def test_list_regions(
    mock_list_regions,
):
    db_session = MagicMock()

    expected = ["region1", "region2"]

    mock_list_regions.return_value = expected

    result = list_regions(
        database_session=db_session
    )

    assert result == expected

    mock_list_regions.assert_called_once_with(
        database_session=db_session
    )


# ==========================================================
# create_access_request
# ==========================================================

@patch(
    "app.routers.access_router.access_service.create_access_request"
)
def test_create_access_request(
    mock_create_request,
):
    db_session = MagicMock()

    request_data = MagicMock()

    request = MagicMock()
    request.state = SimpleNamespace(
        user_id="user123",
        user_name="John Doe",
        user_email="john@test.com",
    )

    expected = MagicMock()

    mock_create_request.return_value = expected

    result = create_access_request(
        request_data=request_data,
        request=request,
        database_session=db_session,
    )

    assert result == expected

    mock_create_request.assert_called_once_with(
        database_session=db_session,
        user_id="user123",
        user_name="John Doe",
        user_email="john@test.com",
        request_data=request_data,
    )


# ==========================================================
# get_my_requests
# ==========================================================

@patch(
    "app.routers.access_router.access_service.get_my_requests"
)
def test_get_my_requests(
    mock_get_requests,
):
    db_session = MagicMock()

    request = MagicMock()
    request.state = SimpleNamespace(
        user_id="user123"
    )

    expected = MagicMock()

    mock_get_requests.return_value = expected

    result = get_my_requests(
        request=request,
        database_session=db_session,
    )

    assert result == expected

    mock_get_requests.assert_called_once_with(
        database_session=db_session,
        user_id="user123",
    )


# ==========================================================
# get_my_access
# ==========================================================

@patch(
    "app.routers.access_router.access_service.get_my_access"
)
def test_get_my_access(
    mock_get_access,
):
    db_session = MagicMock()

    request = MagicMock()
    request.state = SimpleNamespace(
        user_id="user123"
    )

    expected = MagicMock()

    mock_get_access.return_value = expected

    result = get_my_access(
        request=request,
        database_session=db_session,
    )

    assert result == expected

    mock_get_access.assert_called_once_with(
        database_session=db_session,
        user_id="user123",
    )