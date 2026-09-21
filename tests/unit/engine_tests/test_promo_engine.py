import numpy as np
import pandas as pd
import pytest

from unittest.mock import MagicMock, patch

import app.engine.promo_engine as engine

# ==========================================================
# QUARTER HELPERS
# ==========================================================

def test_get_quarter_for_week():
    assert engine.get_quarter_for_week(1) == "Q1"
    assert engine.get_quarter_for_week(20) == "Q2"
    assert engine.get_quarter_for_week(30) == "Q3"
    assert engine.get_quarter_for_week(45) == "Q4"
    assert engine.get_quarter_for_week(99) == "Q4"


# ==========================================================
# PEAK MULTIPLIER
# ==========================================================

def test_get_peak_multiplier_peak():
    assert engine.get_peak_multiplier(45) == 1.40


def test_get_peak_multiplier_default():
    assert engine.get_peak_multiplier(10) == 1.0


def test_add_czech_event_flags():
    df = pd.DataFrame(
        {
            "Year": [2025],
            "Week": [45],
        }
    )

    result = engine.add_czech_event_flags(df)

    assert result["flag_black_november"].iloc[0] == 1.0

def test_is_ready_false():
    original = engine._engine_ready

    try:
        engine._engine_ready = False
        assert engine.is_ready() is False
    finally:
        engine._engine_ready = original

def test_build_x_w():
    engine._X_full = pd.DataFrame(
        {
            "a": [1, 2],
            "b": [3, 4],
        }
    )

    df = pd.DataFrame(
        {
            "discount_oralb": [1, 2],
            "Price_oralb": [3, 4],
            "Qty_oralb": [5, 6],
            "All_media": [7, 8],
            "seasonality": [9, 10],
        }
    )

    X, W = engine.build_X_W(df)

    assert X.shape == (2, 2)
    assert W.shape == (2, 5)

def test_get_cogs_override():
    original = engine._cogs_override

    try:
        engine._cogs_override = {"SKU1": 10}

        assert engine.get_cogs("SKU1") == 10.0

    finally:
        engine._cogs_override = original

def test_get_cogs_from_table():
    original = engine.glc_pe

    try:
        engine.glc_pe = pd.DataFrame(
            {
                "SKU": ["SKU1"],
                "COGS": [5.5],
            }
        )

        assert engine.get_cogs("SKU1") == 5.5

    finally:
        engine.glc_pe = original

def test_get_cogs_missing():
    original = engine.glc_pe

    try:
        engine.glc_pe = pd.DataFrame(
            columns=["SKU", "COGS"]
        )

        with pytest.raises(ValueError):
            engine.get_cogs("BADSKU")

    finally:
        engine.glc_pe = original

def test_derive_unit_cost_legacy():
    result = engine.derive_unit_cost(
        np.array([100.0]),
        25.0,
    )

    assert result > 25

def test_derive_unit_cost_tn():
    result = engine.derive_unit_cost(
        np.array([100.0]),
        25.0,
        economics="tn",
    )

    assert result > 25

class DummyEstimator:
    def effect(
        self,
        X,
        T0,
        T1,
    ):
        return np.array([0.1, 0.2])


def test_predict_qty():
    result = engine.predict_qty(
        DummyEstimator(),
        np.array([10, 10]),
        np.array([9, 8]),
        np.array([[1], [1]]),
        np.array([[1], [1]]),
        np.array([3, 3]),
    )

    assert len(result) == 2   

@patch(
    "app.engine.promo_engine.predict_qty"
)
def test_simulate_scenario_legacy(
    mock_predict,
):
    mock_predict.return_value = np.array(
        [100.0]
    )

    df = pd.DataFrame(
        {
            "Week": [1],
            "log_qty": [1.0],
        }
    )

    result = engine.simulate_scenario(
        est=None,
        discounts=np.array([0.1]),
        unit_cost=10,
        df_sku=df,
        X=np.array([[1]]),
        W=np.array([[1]]),
        t3n_base=np.array([100]),
        qty_base=np.array([50]),
    )

    assert not result.empty

def test_enforce_calendar_rules_empty():
    result = engine.enforce_calendar_rules(
        {},
        pd.DataFrame(),
    )

    assert result == {}

def test_enforce_mandatory_peak_empty():
    assigned, cost = (
        engine.enforce_mandatory_peak_inclusion(
            {},
            pd.DataFrame(),
        )
    )

    assert assigned == {}
    assert cost == {}

def test_portfolio_knapsack_empty():
    assigned, forced = (
        engine.portfolio_knapsack_dp(
            pd.DataFrame(),
            1000,
        )
    )

    assert assigned == {}
    assert forced == {}

def test_aggregate_portfolio_empty():
    result = engine.aggregate_portfolio({})

    assert result.empty

def test_aggregate_portfolio():
    df = pd.DataFrame(
        {
            "week": [1],
            "qty_promo": [10],
            "rev_promo": [20],
            "profit_promo": [30],
            "promo_spend": [5],
            "discount": [0.1],
        }
    )

    result = engine.aggregate_portfolio(
        {"SKU1": df}
    )

    assert len(result) == 1

def test_confidence_tier_high():
    assert (
        engine._confidence_tier(
            100,
            20,
            50,
        )
        == "Definitely do"
    )

def test_confidence_tier_mid():
    assert (
        engine._confidence_tier(
            30,
            20,
            50,
        )
        == "Worth considering"
    )

def test_confidence_tier_low():
    assert (
        engine._confidence_tier(
            10,
            20,
            50,
        )
        == "Minor impact"
    )

def test_get_tier_cells_empty():
    result = engine.get_tier_cells(
        pd.DataFrame()
    )

    assert (
        result["Definitely do"]
        == []
    )

def test_diagnose_q4_none():
    result = engine._diagnose_q4_allocation(
        {}
    )

    assert result is None