"""
Historical data API routes.

Provides historical ROI, revenue, profit, spend,
SKU summaries, weekly trends, and available years.
"""

import logging
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, status

from app.services.historical_data_service import (
    get_available_historical_years,
    get_historical_data,
)


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/api",
    tags=["Historical Data"],
)


@router.get(
    "/historical-data/years",
    response_model=list[str],
    summary="Fetch available historical years",
)
def fetch_historical_years() -> list[str]:
    """
    Return the historical years available for the loaded market.
    """

    try:
        return get_available_historical_years()

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception(
            "Unexpected error while fetching historical years."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "An unexpected error occurred while fetching "
                "historical years."
            ),
        ) from exc


@router.get(
    "/historical-data",
    response_model=dict[str, Any],
    summary="Fetch historical promotion data",
)
def fetch_historical_data(
    year: int = Query(
        ...,
        description="Historical year to retrieve.",
        examples=[2025],
    ),
    classification: str | None = Query(
        default=None,
        description=(
            "Optional product classification: "
            "LRTB, MRTB, or HRTB."
        ),
        examples=["LRTB"],
    ),
    sku: str | None = Query(
        default=None,
        description="Optional exact SKU filter.",
        examples=["HX9911/09"],
    ),
    economics: Literal["tn", "legacy"] = Query(
        default="tn",
        description=(
            "Price reference: "
            "'tn' for Triple Net or "
            "'legacy' for Sell Out."
        ),
        examples=["tn"],
    ),
) -> dict[str, Any]:
    """
    Return historical KPIs, SKU summaries, and weekly trends.

    The model data is reused from the promo engine already loaded
    during application startup.
    """

    try:
        return get_historical_data(
            year=year,
            classification=classification,
            sku=sku,
            economics=economics,
        )

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception(
            "Unexpected error while fetching historical data: %s",
            exc,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "An unexpected error occurred while fetching "
                "historical data."
            ),
        ) from exc