"""SKU listing endpoint."""

import logging

from fastapi import APIRouter, HTTPException, Query, status

from app.engine import promo_engine
from app.engine.promo_engine import (
    compute_reference_spend,
)


logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/skus")
def get_skus(
    bands: str | None = Query(
        default=None,
        description="Comma-separated price bands. Defaults to every band the loaded market declares.",
    ),
) -> dict:
    """Return available SKUs and historical reference spend."""

    if not promo_engine.is_ready() or promo_engine.panel_df is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Promotion engine is still loading.",
        )

    # Unset means every band this market has; the default used to be the
    # three Czech band codes written into the signature.
    requested_bands = (
        [band.strip().upper() for band in bands.split(",") if band.strip()]
        if bands
        else list(promo_engine.PRICE_BANDS)
    )

    if not requested_bands:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one price band must be provided.",
        )

    invalid_bands = [
        band
        for band in requested_bands
        if band not in promo_engine.PRICE_BANDS
    ]

    if invalid_bands:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Invalid price band.",
                "invalid_bands": invalid_bands,
                "allowed_bands": promo_engine.PRICE_BANDS,
            },
        )

    sku_dataframe = (
        promo_engine.panel_df[
            promo_engine.panel_df["Classification"].isin(
                requested_bands
            )
        ][["SKU", "Classification"]]
        .drop_duplicates()
        .sort_values(
            ["Classification", "SKU"]
        )
    )

    sku_list = [
        {
            "sku": str(row["SKU"]),
            "band": str(row["Classification"]),
        }
        for _, row in sku_dataframe.iterrows()
    ]

    all_skus = tuple(sku_dataframe["SKU"].tolist())

    reference_spend = {}

    for year in promo_engine.history_years():
        try:
            reference_spend[str(year)] = round(
                float(
                    compute_reference_spend(
                        all_skus,
                        year,
                    )
                ),
                2,
            )
        except Exception:
            logger.exception(
                "Failed to calculate reference spend for year %s.",
                year,
            )
            reference_spend[str(year)] = 0.0

    return {
        "bands": requested_bands,
        "total_skus": len(sku_list),
        "skus": sku_list,
        "ref_spend": reference_spend,
    }