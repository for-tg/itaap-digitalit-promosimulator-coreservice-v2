"""Access request database models."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database import Base

if TYPE_CHECKING:
    from app.database.models.region import Region


def utc_now() -> datetime:
    """Return the current UTC datetime."""

    return datetime.now(timezone.utc)


class AccessRequestStatus(str, Enum):
    """Supported access request statuses."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AccessRequest(Base):
    """Stores one region access request submitted by a user."""

    __tablename__ = "access_request"

    request_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AccessRequestStatus.PENDING.value,
        index=True,
    )

    requested_by_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    requested_by_email: Mapped[str | None] = mapped_column(
        String(320),
        nullable=True,
    )

    reviewed_by: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    review_comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    regions: Mapped[list["AccessRequestRegion"]] = relationship(
        "AccessRequestRegion",
        back_populates="access_request",
        cascade="all, delete-orphan",
    )


class AccessRequestRegion(Base):
    """Maps one access request to one or more requested regions."""

    __tablename__ = "access_request_region"

    request_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "access_request.request_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    region_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "region.region_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    access_request: Mapped["AccessRequest"] = relationship(
        "AccessRequest",
        back_populates="regions",
    )

    region: Mapped["Region"] = relationship(
        "Region",
    )