from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.routers.historical_data_router import (
    fetch_historical_data,
)


# ==========================================================
# Success
# ==========================================================

@patch(
    "app.routers.historical_data_router.get_historical_data"
)
def test_fetch_historical_data_success(
    mock_get_historical_data,
):
    expected_response = {
        "roi": 1.5,
        "revenue": 1000,
    }

    mock_get_historical_data.return_value = (
        expected_response
    )

    result = fetch_historical_data(
        year=2025,
        classification="LRTB",
        sku="HX9911/09",
        economics="tn",
    )

    assert result == expected_response

    mock_get_historical_data.assert_called_once_with(
        year=2025,
        classification="LRTB",
        sku="HX9911/09",
        economics="tn",
    )


# ==========================================================
# HTTPException passthrough
# ==========================================================

@patch(
    "app.routers.historical_data_router.get_historical_data"
)
def test_fetch_historical_data_http_exception(
    mock_get_historical_data,
):
    mock_get_historical_data.side_effect = (
        HTTPException(
            status_code=404,
            detail="Data not found",
        )
    )

    with pytest.raises(HTTPException) as exc:
        fetch_historical_data(
            year=2025,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Data not found"


# ==========================================================
# Generic exception -> HTTP 500
# ==========================================================

@patch(
    "app.routers.historical_data_router.logger"
)
@patch(
    "app.routers.historical_data_router.get_historical_data"
)
def test_fetch_historical_data_unexpected_exception(
    mock_get_historical_data,
    mock_logger,
):
    mock_get_historical_data.side_effect = Exception(
        "Unexpected failure"
    )

    with pytest.raises(HTTPException) as exc:
        fetch_historical_data(
            year=2025,
            economics="tn",
        )

    assert exc.value.status_code == 500

    assert (
        exc.value.detail
        == (
            "An unexpected error occurred while fetching "
            "historical data."
        )
    )

    mock_logger.exception.assert_called_once_with(
        "Unexpected error while fetching historical data."
    )