from unittest.mock import MagicMock, patch

from app.routers.dashboard_router import (
    get_dashboard,
)


# ==========================================================
# get_dashboard
# ==========================================================

@patch(
    "app.routers.dashboard_router.dashboard_service.get_dashboard"
)
def test_get_dashboard(
    mock_get_dashboard,
):
    db_session = MagicMock()

    expected_response = MagicMock()

    mock_get_dashboard.return_value = (
        expected_response
    )

    result = get_dashboard(
        user_id="user123",
        database_session=db_session,
    )

    assert result == expected_response

    mock_get_dashboard.assert_called_once_with(
        database_session=db_session,
        user_id="user123",
    )