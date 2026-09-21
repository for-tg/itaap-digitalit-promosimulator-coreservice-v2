"""Database operations for SKU master records."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.sku import SKU


def get_sku_by_code(
    database_session: Session,
    sku_code: str,
) -> SKU | None:
    """Return a SKU by its exact code."""

    statement = select(SKU).where(
        SKU.sku_code == sku_code,
    )

    return database_session.scalar(statement)


def get_sku_by_id(
    database_session: Session,
    sku_id: str,
) -> SKU | None:
    """Return one active SKU by ID."""

    statement = select(SKU).where(
        SKU.sku_id == sku_id,
        SKU.is_active.is_(True),
    )

    return database_session.scalar(statement)


def list_active_skus(
    database_session: Session,
    classification: str | None = None,
) -> list[SKU]:
    """Return active SKU master records."""

    statement = select(SKU).where(
        SKU.is_active.is_(True),
    )

    if classification:
        statement = statement.where(
            SKU.classification == classification,
        )

    statement = statement.order_by(
        SKU.classification.asc(),
        SKU.sku_code.asc(),
    )

    return list(
        database_session.scalars(statement).all()
    )


def list_all_skus(
    database_session: Session,
) -> list[SKU]:
    """Return all SKU records, including inactive ones."""

    statement = select(SKU).order_by(
        SKU.sku_code.asc(),
    )

    return list(
        database_session.scalars(statement).all()
    )


def create_sku(
    database_session: Session,
    sku_code: str,
    sku_name: str | None,
    classification: str | None,
) -> SKU:
    """Create one SKU master record."""

    sku = SKU(
        sku_code=sku_code,
        sku_name=sku_name,
        classification=classification,
        is_active=True,
    )

    database_session.add(sku)

    return sku


def update_sku(
    sku: SKU,
    sku_name: str | None,
    classification: str | None,
) -> bool:
    """Update a SKU and return whether any value changed."""

    changed = False

    if sku.sku_name != sku_name:
        sku.sku_name = sku_name
        changed = True

    if sku.classification != classification:
        sku.classification = classification
        changed = True

    if not sku.is_active:
        sku.is_active = True
        changed = True

    return changed


def deactivate_missing_skus(
    known_skus: list[SKU],
    active_sku_codes: set[str],
) -> int:
    """Deactivate SKUs that are no longer present in the source."""

    deactivated = 0

    for sku in known_skus:
        if (
            sku.is_active
            and sku.sku_code not in active_sku_codes
        ):
            sku.is_active = False
            deactivated += 1

    return deactivated


def commit_sku_changes(
    database_session: Session,
) -> None:
    """Commit SKU synchronization changes."""

    database_session.commit()