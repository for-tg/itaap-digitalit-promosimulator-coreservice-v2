"""Pydantic schemas for SKU master APIs."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SKUResponse(BaseModel):
    """Response schema for one SKU master record."""

    sku_id: str
    sku_code: str
    sku_name: str | None
    classification: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


class SKUListResponse(BaseModel):
    """Response schema for listing SKU master records."""

    total: int
    skus: list[SKUResponse]


class SKUSyncResponse(BaseModel):
    """Response schema for SKU synchronization."""

    source: str = Field(
        default="promo_engine.panel_df",
    )
    inserted: int
    updated: int
    unchanged: int
    deactivated: int
    total_active: int