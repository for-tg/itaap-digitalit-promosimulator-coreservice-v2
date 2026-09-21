"""Business logic for SKU master management."""

import logging

import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database.repositories import sku_repository
from app.engine import promo_engine
from app.schemas.sku import (
    SKUListResponse,
    SKUResponse,
    SKUSyncResponse,
)


logger = logging.getLogger(__name__)


def _valid_classifications() -> set:
    """The loaded market's price bands, from meta.segment_labels."""
    return set(promo_engine.PRICE_BANDS)


def sync_skus_from_model(
    database_session: Session,
) -> SKUSyncResponse:
    """Synchronize SKU master records from the loaded panel data."""

    if not promo_engine.is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Promotion engine is still loading.",
        )

    panel_df = promo_engine.panel_df

    required_columns = {
        "SKU",
        "Classification",
    }

    missing_columns = (
        required_columns - set(panel_df.columns)
    )

    if missing_columns:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "SKU source data is missing required columns: "
                + ", ".join(sorted(missing_columns))
            ),
        )

    source_df = panel_df[
        ["SKU", "Classification"]
    ].copy()

    source_df["SKU"] = (
        source_df["SKU"]
        .astype(str)
        .str.strip()
    )

    source_df["Classification"] = (
        source_df["Classification"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    source_df = source_df[
        source_df["SKU"].ne("")
        & source_df["Classification"].isin(
            _valid_classifications()
        )
    ]

    source_df = (
        source_df
        .drop_duplicates(
            subset=["SKU"],
            keep="first",
        )
        .sort_values("SKU")
    )

    if source_df.empty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No valid SKUs were found in the loaded model data.",
        )

    existing_skus = sku_repository.list_all_skus(
        database_session=database_session,
    )

    existing_by_code = {
        sku.sku_code: sku
        for sku in existing_skus
    }

    inserted = 0
    updated = 0
    unchanged = 0

    active_sku_codes: set[str] = set()

    for _, row in source_df.iterrows():
        sku_code = str(row["SKU"])
        classification = str(
            row["Classification"]
        )

        active_sku_codes.add(sku_code)

        existing_sku = existing_by_code.get(
            sku_code
        )

        if existing_sku is None:
            sku_repository.create_sku(
                database_session=database_session,
                sku_code=sku_code,
                sku_name=None,
                classification=classification,
            )
            inserted += 1
            continue

        changed = sku_repository.update_sku(
            sku=existing_sku,
            sku_name=existing_sku.sku_name,
            classification=classification,
        )

        if changed:
            updated += 1
        else:
            unchanged += 1

    deactivated = (
        sku_repository.deactivate_missing_skus(
            known_skus=existing_skus,
            active_sku_codes=active_sku_codes,
        )
    )

    try:
        sku_repository.commit_sku_changes(
            database_session=database_session,
        )
    except Exception as exc:
        database_session.rollback()

        logger.exception(
            "Failed to synchronize SKU master data."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to synchronize SKU master data.",
        ) from exc

    total_active = len(
        sku_repository.list_active_skus(
            database_session=database_session,
        )
    )

    return SKUSyncResponse(
        inserted=inserted,
        updated=updated,
        unchanged=unchanged,
        deactivated=deactivated,
        total_active=total_active,
    )


def list_skus(
    database_session: Session,
    classification: str | None = None,
) -> SKUListResponse:
    """Return active SKU master records."""

    cleaned_classification = None

    if classification:
        cleaned_classification = (
            classification.strip().upper()
        )

        if (
            cleaned_classification
            not in _valid_classifications()
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Invalid classification. Supported values are "
                    + ", ".join(promo_engine.PRICE_BANDS) + "."
                ),
            )

    skus = sku_repository.list_active_skus(
        database_session=database_session,
        classification=cleaned_classification,
    )

    sku_responses = [
        SKUResponse.model_validate(sku)
        for sku in skus
    ]

    return SKUListResponse(
        total=len(sku_responses),
        skus=sku_responses,
    )


def get_sku(
    database_session: Session,
    sku_id: str,
) -> SKUResponse:
    """Return one active SKU master record."""

    cleaned_sku_id = sku_id.strip()

    if not cleaned_sku_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="sku_id must not be empty.",
        )

    sku = sku_repository.get_sku_by_id(
        database_session=database_session,
        sku_id=cleaned_sku_id,
    )

    if sku is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SKU not found.",
        )

    return SKUResponse.model_validate(sku)