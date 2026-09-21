"""Pydantic schemas for region access APIs."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class AccessRequestStatus(str, Enum):
    """Supported access request statuses."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class RegionResponse(BaseModel):
    """Region master response."""

    region_id: str
    region_code: str
    region_name: str


class CreateAccessRequest(BaseModel):
    """Request payload for requesting access to regions."""

    region_ids: list[str] = Field(
        ...,
        min_length=1,
    )

    @field_validator(
        "region_ids",
        mode="before",
    )
    @classmethod
    def clean_region_ids(
        cls,
        value: list[str],
    ) -> list[str]:
        """Trim region IDs and remove duplicates."""

        if not value:
            return []

        cleaned_values: list[str] = []

        for region_id in value:
            cleaned_region_id = str(region_id).strip()

            if (
                cleaned_region_id
                and cleaned_region_id not in cleaned_values
            ):
                cleaned_values.append(
                    cleaned_region_id
                )

        return cleaned_values


class AccessRequestRegionResponse(BaseModel):
    """Region details inside an access request."""

    region_id: str
    region_code: str
    region_name: str


class AccessRequestResponse(BaseModel):
    """Access request response."""

    request_id: str
    user_id: str
    requested_by_name: str | None
    requested_by_email: str | None
    status: AccessRequestStatus
    regions: list[AccessRequestRegionResponse]
    reviewed_by: str | None
    review_comment: str | None
    created_at: datetime
    reviewed_at: datetime | None
    updated_at: datetime


class AccessRequestListResponse(BaseModel):
    """List of access requests."""

    total: int
    requests: list[AccessRequestResponse]


class ReviewAccessRequest(BaseModel):
    """Admin request payload for approve/reject."""

    comment: str | None = Field(
        default=None,
        max_length=1000,
    )

    @field_validator(
        "comment",
        mode="before",
    )
    @classmethod
    def clean_comment(
        cls,
        value: str | None,
    ) -> str | None:
        """Trim optional admin comment."""

        if isinstance(value, str):
            value = value.strip()

        return value or None


class UserRegionAccessResponse(BaseModel):
    """One region access entry for a user."""

    access_id: str
    user_id: str
    region_id: str
    region_code: str
    region_name: str
    is_active: bool
    granted_by: str | None
    granted_at: datetime
    revoked_by: str | None
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UserRegionAccessListResponse(BaseModel):
    """List of user-region access entries."""

    total: int
    access: list[UserRegionAccessResponse]


class MyAccessResponse(BaseModel):
    """Current user's access overview."""

    user_id: str
    active_regions: list[UserRegionAccessResponse]
    pending_request: AccessRequestResponse | None