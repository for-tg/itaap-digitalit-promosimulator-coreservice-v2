"""SKU master API routes."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.schemas.sku import (
    SKUListResponse,
    SKUResponse,
    SKUSyncResponse,
)
from app.services import sku_service


router = APIRouter(
    prefix="/api/skus",
    tags=["SKU Master"],
)


@router.post(
    "/sync",
    response_model=SKUSyncResponse,
    status_code=status.HTTP_200_OK,
    summary="Synchronize SKU master data",
)
def sync_skus(
    database_session: Session = Depends(get_db),
) -> SKUSyncResponse:
    """Synchronize SKU master data from the loaded pickle."""

    return sku_service.sync_skus_from_model(
        database_session=database_session,
    )


@router.get(
    "/master",
    response_model=SKUListResponse,
    summary="List SKU master records",
)
def list_skus(
    classification: str | None = Query(
        default=None,
        description=(
            "Optional classification filter: "
            "LRTB, MRTB, or HRTB."
        ),
    ),
    database_session: Session = Depends(get_db),
) -> SKUListResponse:
    """Return active SKU master records."""

    return sku_service.list_skus(
        database_session=database_session,
        classification=classification,
    )


@router.get(
    "/master/{sku_id}",
    response_model=SKUResponse,
    summary="Get SKU master record",
)
def get_sku(
    sku_id: str,
    database_session: Session = Depends(get_db),
) -> SKUResponse:
    """Return one active SKU master record."""

    return sku_service.get_sku(
        database_session=database_session,
        sku_id=sku_id,
    )