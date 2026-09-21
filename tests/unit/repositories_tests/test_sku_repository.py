from unittest.mock import MagicMock, patch

from app.database.repositories.sku_repository import (
    commit_sku_changes,
    create_sku,
    deactivate_missing_skus,
    get_sku_by_code,
    get_sku_by_id,
    list_active_skus,
    list_all_skus,
    update_sku,
)


# ==========================================================
# get_sku_by_code
# ==========================================================

def test_get_sku_by_code():
    session = MagicMock()

    sku = MagicMock()
    session.scalar.return_value = sku

    result = get_sku_by_code(
        database_session=session,
        sku_code="SKU001",
    )

    assert result == sku
    session.scalar.assert_called_once()


# ==========================================================
# get_sku_by_id
# ==========================================================

def test_get_sku_by_id():
    session = MagicMock()

    sku = MagicMock()
    session.scalar.return_value = sku

    result = get_sku_by_id(
        database_session=session,
        sku_id="1",
    )

    assert result == sku
    session.scalar.assert_called_once()


# ==========================================================
# list_active_skus
# ==========================================================

def test_list_active_skus_without_classification():
    session = MagicMock()

    skus = [MagicMock(), MagicMock()]
    session.scalars.return_value.all.return_value = skus

    result = list_active_skus(
        database_session=session
    )

    assert result == skus


def test_list_active_skus_with_classification():
    session = MagicMock()

    skus = [MagicMock()]
    session.scalars.return_value.all.return_value = skus

    result = list_active_skus(
        database_session=session,
        classification="Beverage",
    )

    assert result == skus


# ==========================================================
# list_all_skus
# ==========================================================

def test_list_all_skus():
    session = MagicMock()

    skus = [MagicMock(), MagicMock()]
    session.scalars.return_value.all.return_value = skus

    result = list_all_skus(
        database_session=session
    )

    assert result == skus


# ==========================================================
# create_sku
# ==========================================================

@patch(
    "app.database.repositories.sku_repository.SKU"
)
def test_create_sku(mock_sku):
    session = MagicMock()

    sku_obj = MagicMock()
    mock_sku.return_value = sku_obj

    result = create_sku(
        database_session=session,
        sku_code="SKU001",
        sku_name="Coke",
        classification="Beverage",
    )

    assert result == sku_obj

    mock_sku.assert_called_once_with(
        sku_code="SKU001",
        sku_name="Coke",
        classification="Beverage",
        is_active=True,
    )

    session.add.assert_called_once_with(
        sku_obj
    )


# ==========================================================
# update_sku
# ==========================================================

def test_update_sku_no_changes():
    sku = MagicMock()

    sku.sku_name = "Coke"
    sku.classification = "Beverage"
    sku.is_active = True

    changed = update_sku(
        sku=sku,
        sku_name="Coke",
        classification="Beverage",
    )

    assert changed is False


def test_update_sku_name_changed():
    sku = MagicMock()

    sku.sku_name = "Old Name"
    sku.classification = "Beverage"
    sku.is_active = True

    changed = update_sku(
        sku=sku,
        sku_name="New Name",
        classification="Beverage",
    )

    assert changed is True
    assert sku.sku_name == "New Name"


def test_update_sku_classification_changed():
    sku = MagicMock()

    sku.sku_name = "Coke"
    sku.classification = "Old Class"
    sku.is_active = True

    changed = update_sku(
        sku=sku,
        sku_name="Coke",
        classification="New Class",
    )

    assert changed is True
    assert sku.classification == "New Class"


def test_update_sku_reactivate():
    sku = MagicMock()

    sku.sku_name = "Coke"
    sku.classification = "Beverage"
    sku.is_active = False

    changed = update_sku(
        sku=sku,
        sku_name="Coke",
        classification="Beverage",
    )

    assert changed is True
    assert sku.is_active is True


def test_update_sku_multiple_changes():
    sku = MagicMock()

    sku.sku_name = "Old"
    sku.classification = "OldClass"
    sku.is_active = False

    changed = update_sku(
        sku=sku,
        sku_name="New",
        classification="NewClass",
    )

    assert changed is True
    assert sku.sku_name == "New"
    assert sku.classification == "NewClass"
    assert sku.is_active is True


# ==========================================================
# deactivate_missing_skus
# ==========================================================

def test_deactivate_missing_skus():
    sku1 = MagicMock()
    sku1.is_active = True
    sku1.sku_code = "SKU1"

    sku2 = MagicMock()
    sku2.is_active = True
    sku2.sku_code = "SKU2"

    sku3 = MagicMock()
    sku3.is_active = False
    sku3.sku_code = "SKU3"

    result = deactivate_missing_skus(
        known_skus=[sku1, sku2, sku3],
        active_sku_codes={"SKU1"},
    )

    assert result == 1
    assert sku2.is_active is False


def test_deactivate_missing_skus_none():
    sku1 = MagicMock()
    sku1.is_active = True
    sku1.sku_code = "SKU1"

    sku2 = MagicMock()
    sku2.is_active = True
    sku2.sku_code = "SKU2"

    result = deactivate_missing_skus(
        known_skus=[sku1, sku2],
        active_sku_codes={"SKU1", "SKU2"},
    )

    assert result == 0


# ==========================================================
# commit_sku_changes
# ==========================================================

def test_commit_sku_changes():
    session = MagicMock()

    commit_sku_changes(session)

    session.commit.assert_called_once()