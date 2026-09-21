# -*- coding: utf-8 -*-
"""
Promo Engine – ML/optimizer logic ported from promo_backend.py.
No Streamlit dependency. Model/data are injected via init_engine().
"""

import logging

import numpy as np
import pandas as pd
from collections import defaultdict

from threading import Lock

_engine_lock = Lock()
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# 1. CONSTANTS
# ─────────────────────────────────────────────────────────────────────

# Every value in this section is a MARKET DEFAULT. When the loaded artifact
# carries a `meta` block, _apply_market_meta() overwrites the ones meta
# declares. An artifact without meta keeps these values, so older pickles
# behave exactly as they did before.

FEATURE_COLS = [
    "Classification", "SKU_ctg",
    "flag_black_november", "flag_christmas", "flag_jan_clearance",
    "flag_mothers_day", "flag_fathers_childrens", "flag_summer_clearance",
    "flag_valentines", "flag_easter",
    "Year",
    "is_imputed",
    "hist_promo_intensity",
    "seasonal_vol_index",
    "was_promo_last_week",
    "consecutive_promo_weeks",
    "weeks_since_last_promo",
]
# Columns FEATURE_COLS one-hot encodes. Everything else in it is numeric.
CATEGORICAL_COLS = ["Classification", "SKU_ctg"]
CONFOUNDER_NAMES = [
    "discount_oralb",
    "Price_oralb",
    "Qty_oralb",
    "All_media",
    "seasonality",
]

TPW_RATE = 0.01
AP_RATE = 0.16
OFSE_RATE = 0.07
OTHER_RATE = TPW_RATE + AP_RATE + OFSE_RATE
# The same legacy rate as a single declared figure. Kept separate from
# OTHER_RATE because the sum above is 0.24000000000000002 in binary floating
# point, and historical_data_service has always used the exact literal.
LEGACY_TRADE_COST_RATE = 0.24

# Triple-Net economics
VAT_RATE = 1.21
TRADE_SPEND_RATE = 0.29965
K_BRIDGE = (1.0 / VAT_RATE) * (1.0 - TRADE_SPEND_RATE)
TPW_RATE_TN = 0.0131
OFSE_RATE_TN = 0.0664
CONTRIB_COST_RATE = TPW_RATE_TN + OFSE_RATE_TN

DELTA_CLIP = (-3.0, 3.0)
DISCOUNT_GRID_ALL = np.concatenate([[0.0], np.arange(5, 41, 1) / 100.0])
MAX_DISCOUNT_DEFAULT = 0.25
PRICE_BANDS = ["LRTB", "MRTB", "HRTB"]

# Market identity used in generated copy.
CURRENCY_CODE = "CZK"
CURRENCY_SYMBOL = ""
PRICE_DECIMALS = 0
PORTFOLIO_LABEL = "Philips Oral Care portfolio"

# Calendar. HISTORY_YEARS and PLAN_YEAR stay None until an artifact declares
# them; callers fall back to reading the panel, as they did before.
WEEKS_PER_YEAR = 52
HISTORY_YEARS = None
PLAN_YEAR = None

# Event calendar. Each entry is {"col", "label", "weeks", optional
# "weeks_by_year"}. Only used when the panel arrives without flag columns.
EVENT_FLAGS = [
    {"col": "flag_black_november", "label": "Black November", "weeks": [45, 46, 47, 48]},
    {"col": "flag_christmas", "label": "Christmas", "weeks": [49, 50, 51]},
    {"col": "flag_jan_clearance", "label": "January clearance", "weeks": [1, 2, 3]},
    {"col": "flag_mothers_day", "label": "Mother's Day", "weeks": [19, 20]},
    {"col": "flag_fathers_childrens", "label": "Father's / Children's Day", "weeks": [22, 23, 24]},
    {"col": "flag_summer_clearance", "label": "Summer clearance", "weeks": [26, 27, 28]},
    {"col": "flag_valentines", "label": "Valentine's Day", "weeks": [6, 7]},
    {"col": "flag_easter", "label": "Easter", "weeks": [],
     "weeks_by_year": {"2022": [15, 16], "2023": [14, 15], "2024": [13, 14],
                       "2025": [15, 16], "2026": [14, 15]}},
]

QUARTER_WEEKS = {
    "Q1": (1, 13),
    "Q2": (14, 26),
    "Q3": (27, 39),
    "Q4": (40, 52),
}


def _apply_market_meta(meta: dict | None) -> None:
    """Overwrite the market defaults above from the artifact's meta block.

    Anything meta does not declare keeps its default, so an artifact with no
    meta block produces exactly the behaviour this module had before.
    """
    global FEATURE_COLS, CATEGORICAL_COLS, PRICE_BANDS, DELTA_CLIP
    global DISCOUNT_GRID_ALL, MAX_DISCOUNT_DEFAULT
    global TPW_RATE, AP_RATE, OFSE_RATE, OTHER_RATE, LEGACY_TRADE_COST_RATE
    global VAT_RATE, TRADE_SPEND_RATE, K_BRIDGE, TPW_RATE_TN, OFSE_RATE_TN, CONTRIB_COST_RATE
    global PEAK_WEEK_PRIORITY, _MANDATORY_CAMPAIGN_WEEKS
    global ALL_PEAK_HALO_WEEKS, CAMPAIGN_WINDOWS
    global CURRENCY_CODE, CURRENCY_SYMBOL, PRICE_DECIMALS, PORTFOLIO_LABEL
    global WEEKS_PER_YEAR, HISTORY_YEARS, PLAN_YEAR, EVENT_FLAGS, QUARTER_WEEKS

    if not isinstance(meta, dict):
        return

    if meta.get("segment_labels"):
        PRICE_BANDS = list(meta["segment_labels"])

    spec = meta.get("feature_spec") or {}
    if spec.get("categorical") or spec.get("numeric"):
        CATEGORICAL_COLS = list(spec.get("categorical") or [])
        FEATURE_COLS = CATEGORICAL_COLS + list(spec.get("numeric") or [])

    econ = meta.get("economics") or {}
    TPW_RATE = float(econ.get("legacy_tpw_rate", TPW_RATE))
    AP_RATE = float(econ.get("legacy_ap_rate", AP_RATE))
    OFSE_RATE = float(econ.get("legacy_ofse_rate", OFSE_RATE))
    # The legacy cost-on-price rate. Declared directly when meta carries it,
    # otherwise the sum of its three parts, which is how it was built before.
    OTHER_RATE = float(econ.get("legacy_trade_cost_rate", TPW_RATE + AP_RATE + OFSE_RATE))
    LEGACY_TRADE_COST_RATE = float(econ.get("legacy_trade_cost_rate", LEGACY_TRADE_COST_RATE))
    VAT_RATE = float(econ.get("vat_rate", VAT_RATE))
    TRADE_SPEND_RATE = float(econ.get("trade_spend_rate", TRADE_SPEND_RATE))
    K_BRIDGE = (1.0 / VAT_RATE) * (1.0 - TRADE_SPEND_RATE)
    TPW_RATE_TN = float(econ.get("tpw_rate_tn", TPW_RATE_TN))
    OFSE_RATE_TN = float(econ.get("ofse_rate_tn", OFSE_RATE_TN))
    CONTRIB_COST_RATE = TPW_RATE_TN + OFSE_RATE_TN

    if meta.get("delta_clip"):
        lo, hi = meta["delta_clip"]
        DELTA_CLIP = (float(lo), float(hi))

    grid = meta.get("discount_grid") or {}
    if grid:
        step = float(grid.get("step", 0.01))
        lo = float(grid.get("min", 0.05))
        hi = float(grid.get("max", 0.40))
        steps = np.arange(round(lo / step), round(hi / step) + 1) * step
        DISCOUNT_GRID_ALL = (
            np.concatenate([[0.0], steps]) if grid.get("include_zero", True) else steps
        )
    if meta.get("max_discount_default") is not None:
        MAX_DISCOUNT_DEFAULT = float(meta["max_discount_default"])

    if meta.get("peak_week_priority"):
        PEAK_WEEK_PRIORITY = {
            frozenset(int(w) for w in entry["weeks"]): float(entry["multiplier"])
            for entry in meta["peak_week_priority"]
        }
        ALL_PEAK_HALO_WEEKS = frozenset(w for week_set in PEAK_WEEK_PRIORITY for w in week_set)
        CAMPAIGN_WINDOWS = _build_campaign_windows()
    if meta.get("mandatory_campaign_weeks"):
        _MANDATORY_CAMPAIGN_WEEKS = frozenset(int(w) for w in meta["mandatory_campaign_weeks"])

    CURRENCY_CODE = meta.get("currency_code") or CURRENCY_CODE
    CURRENCY_SYMBOL = meta.get("currency_symbol") or CURRENCY_SYMBOL

    if meta.get("price_decimals") is not None:
        PRICE_DECIMALS = int(meta["price_decimals"])

    PORTFOLIO_LABEL = meta.get("portfolio_label") or PORTFOLIO_LABEL

    if meta.get("weeks_per_year"):
        WEEKS_PER_YEAR = int(meta["weeks_per_year"])
        # Q1-Q3 are fixed 13-week quarters; Q4 absorbs the 53rd week when a
        # market plans on an ISO year that has one.
        QUARTER_WEEKS = dict(QUARTER_WEEKS, Q4=(40, WEEKS_PER_YEAR))
    if meta.get("history_years"):
        HISTORY_YEARS = [int(y) for y in meta["history_years"]]
    if meta.get("plan_year") is not None:
        PLAN_YEAR = int(meta["plan_year"])

    if meta.get("event_flags"):
        EVENT_FLAGS = list(meta["event_flags"])

COLORS = {
    "Base": "#2563eb",
    "Optimal": "#16a34a",
    "Actual": "#9333ea",
}


def history_years() -> list:
    """Observed history years for the loaded market.

    meta.history_years when declared, otherwise every panel year that
    carries actuals — the plan year has none, which is what excludes it.
    """
    if HISTORY_YEARS:
        return list(HISTORY_YEARS)
    if panel_df is None:
        return []
    years = panel_df["Year"]
    if "Price" in panel_df.columns:
        observed = panel_df.loc[panel_df["Price"].notna(), "Year"]
        if not observed.empty:
            years = observed
    return sorted(int(y) for y in years.unique())




def currency_info() -> dict[str, str]:
    """Return currency information for the loaded market."""

    return {
        "code": str(CURRENCY_CODE),
        "symbol": str(CURRENCY_SYMBOL),
    }



def get_quarter_for_week(week: int) -> str:
    for q, (w_start, w_end) in QUARTER_WEEKS.items():
        if w_start <= week <= w_end:
            return q
    return "Q4"


MONTH_TO_WEEK = {
    "Jan": 1, "Feb": 5, "Mar": 9, "Apr": 14,
    "May": 18, "Jun": 22, "Jul": 27, "Aug": 31,
    "Sep": 36, "Oct": 40, "Nov": 45, "Dec": 49,
}

# ─────────────────────────────────────────────────────────────────────
# 2. ENGINE STATE (populated by init_engine)
# ─────────────────────────────────────────────────────────────────────

panel_df: pd.DataFrame = None
glc_pe: pd.DataFrame = None
est_price_f = None
_feature_names_pkl: list = None
_confounder_names_pkl: list = None
_cogs_override: dict = {}
_X_full: pd.DataFrame = None
_engine_ready = False


def is_ready() -> bool:
    return _engine_ready


# def init_engine(data: dict, cogs_override: dict = None):
#     """Initialize the engine with loaded model data. Called once at startup."""
#     global panel_df, glc_pe, est_price_f, _feature_names_pkl
#     global _confounder_names_pkl, _cogs_override, _X_full, _engine_ready

#     panel_df = data["panel_df"]
#     glc_pe = data["glc_pe"]
#     est_price_f = data["model"]
#     _feature_names_pkl = data["feature_names"]
#     _confounder_names_pkl = data["confounder_names"]
#     _cogs_override = cogs_override or {}

#     _prepare_features()
#     _engine_ready = True


# # ─────────────────────────────────────────────────────────────────────
# # 3. FEATURE MATRIX
# # ─────────────────────────────────────────────────────────────────────

# ```python
def init_engine(
    data: dict,
    cogs_override: dict | None = None,
) -> None:
    """Initialize the engine with loaded model data once."""

    global panel_df, glc_pe, est_price_f, _feature_names_pkl
    global _confounder_names_pkl, _cogs_override, _X_full, _engine_ready
    global CONFOUNDER_NAMES

    with _engine_lock:
        if _engine_ready:
            return

        # Market values come from the artifact before anything reads them.
        _apply_market_meta(data.get("meta"))

        panel_df = data["panel_df"]
        glc_pe = data["glc_pe"]
        est_price_f = data["model"]
        _feature_names_pkl = data["feature_names"]
        _confounder_names_pkl = data["confounder_names"]
        _cogs_override = cogs_override or {}

        # The fitted model defines the confounders; the simulator follows it.
        CONFOUNDER_NAMES = list(_confounder_names_pkl)

        _prepare_features()

        missing_w = [c for c in CONFOUNDER_NAMES if c not in panel_df.columns]
        if missing_w:
            raise ValueError(
                "panel_df is missing confounder columns the model was fitted "
                f"with: {missing_w}"
            )

        _engine_ready = True
# ```


def add_event_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Stamp the market's event flags onto a panel that arrives without them.

    Driven by EVENT_FLAGS, which meta.event_flags supplies. An entry may carry
    `weeks_by_year` for a moveable feast; `weeks` is used for every other year.
    """
    df = df.copy()
    for spec in EVENT_FLAGS:
        col = spec.get("col")
        if not col:
            continue
        weeks = [int(w) for w in (spec.get("weeks") or [])]
        by_year = spec.get("weeks_by_year") or {}
        if by_year:
            mask = pd.Series(False, index=df.index)
            for yr, yr_weeks in by_year.items():
                mask |= (df["Year"] == int(yr)) & df["Week"].isin(
                    [int(w) for w in yr_weeks]
                )
            years_covered = {int(y) for y in by_year}
            if weeks:
                mask |= ~df["Year"].isin(years_covered) & df["Week"].isin(weeks)
        else:
            mask = df["Week"].isin(weeks)
        df[col] = mask.astype(float)
    return df


def _prepare_features():
    """Build the one-hot feature matrix from panel_df. Called by init_engine."""
    global panel_df, _X_full

    flag_cols_needed = [
        spec["col"] for spec in EVENT_FLAGS if spec.get("col")
    ]
    if flag_cols_needed and not all(c in panel_df.columns for c in flag_cols_needed):
        panel_df = add_event_flags(panel_df)

    for col, default in [
        ("is_imputed", 0.0),
        ("hist_promo_intensity", 0.0),
        ("seasonal_vol_index", 1.0),
        ("was_promo_last_week", 0.0),
        ("consecutive_promo_weeks", 0.0),
        ("weeks_since_last_promo", 10.0),
    ]:
        if col not in panel_df.columns:
            panel_df[col] = default

    _X_raw = pd.get_dummies(
        panel_df[CATEGORICAL_COLS],
        columns=CATEGORICAL_COLS,
        drop_first=True,
    )
    _numeric_feat = [c for c in FEATURE_COLS if c not in CATEGORICAL_COLS]
    _X_full_local = pd.concat(
        [_X_raw.reset_index(drop=True),
         panel_df[_numeric_feat].reset_index(drop=True)],
        axis=1,
    ).astype(float)

    _extra = set(_X_full_local.columns) - set(_feature_names_pkl)
    if _extra:
        raise ValueError(f"X has unexpected columns not seen during training: {_extra}")
    # The reverse case is silent otherwise: reindex fills a feature the model
    # was fitted on with zeros on every row. That is correct for a one-hot
    # level with no rows in this panel, and wrong for a real numeric feature,
    # so it is reported rather than raised.
    _absent = sorted(set(_feature_names_pkl) - set(_X_full_local.columns))
    if _absent:
        logger.warning(
            "X is missing %d column(s) the model was fitted with; they are "
            "zero-filled on every row: %s",
            len(_absent), _absent,
        )
    _X_full = _X_full_local.reindex(columns=_feature_names_pkl, fill_value=0.0)


def build_X_W(df: pd.DataFrame):
    X = _X_full.loc[df.index].values
    W = df[CONFOUNDER_NAMES].values
    return X, W


# ─────────────────────────────────────────────────────────────────────
# 4. DATA-ACCESS HELPERS
# ─────────────────────────────────────────────────────────────────────
def get_sku_slice(
    sku: str,
    start_year: int, start_week: int,
    n_weeks: int = None,
    end_year: int = None, end_week: int = None,
) -> pd.DataFrame:
    start_key = start_year * 100 + start_week
    df = (
        panel_df[panel_df["SKU"] == sku]
        .assign(yearweek=lambda d: d["Year"] * 100 + d["Week"])
        .pipe(lambda d: d[d["yearweek"] >= start_key])
        .sort_values("yearweek")
    )
    if end_year is not None and end_week is not None:
        end_key = end_year * 100 + end_week
        df = df[df["yearweek"] <= end_key]
    if n_weeks is not None:
        df = df.head(n_weeks)
    return df.drop(columns=["yearweek"]).copy()


def get_cogs(sku: str) -> float:
    if sku in _cogs_override:
        return float(_cogs_override[sku])
    row = glc_pe[glc_pe["SKU"] == sku]
    if row.empty:
        raise ValueError(f"No COGS for SKU: {sku} — add it to COGS_per_SKU.csv")
    return float(row.iloc[0]["COGS"])


def derive_unit_cost(t3n_base: np.ndarray, cogs: float, economics: str = "legacy") -> float:
    """Compute per-unit cost for profit calculations.

    economics="legacy": COGS + 24% × mean(sell-out Price_base) — original formula.
    economics="tn":     COGS + 7.95% × mean(TN_base) — correct Philips waterfall
                        (TPW + OFSE on Triple Net, excluding A&P).
    """
    if economics == "tn":
        tn_mean = float(t3n_base.mean()) * K_BRIDGE
        return cogs + CONTRIB_COST_RATE * tn_mean
    # Legacy: t3n_base here is actually sell-out Price_base (misnomer)
    p_mean = float(t3n_base.mean())
    return cogs + OTHER_RATE * p_mean


# ─────────────────────────────────────────────────────────────────────
# 5. CAUSAL ML PREDICTION
# ─────────────────────────────────────────────────────────────────────
def predict_qty(
    est,
    log_price_base: np.ndarray,
    log_price_new: np.ndarray,
    X: np.ndarray,
    W: np.ndarray,
    log_qty_base: np.ndarray,
) -> np.ndarray:
    delta = est.effect(
        X=X,
        T0=np.asarray(log_price_base).reshape(-1),
        T1=np.asarray(log_price_new).reshape(-1),
    )
    return np.exp(log_qty_base + np.clip(delta, *DELTA_CLIP))


# ─────────────────────────────────────────────────────────────────────
# 6. SIMULATION
# ─────────────────────────────────────────────────────────────────────
def simulate_scenario(
    est,
    discounts:  np.ndarray,
    unit_cost:  float,
    df_sku:     pd.DataFrame,
    X:          np.ndarray,
    W:          np.ndarray,
    t3n_base:   np.ndarray,
    qty_base:   np.ndarray,
    economics:  str = "legacy",
) -> pd.DataFrame:
    # EconML always runs on sell-out (shelf) prices — that's what it was trained on
    t3n_scn = t3n_base * (1.0 - discounts)
    qty_scn = predict_qty(est, np.log(t3n_base), np.log(t3n_scn), X, W, np.log(qty_base))

    qty_actual = (
        np.exp(df_sku["log_qty"].values)
        if "log_qty" in df_sku.columns
        else np.full_like(qty_scn, np.nan)
    )

    if economics == "tn":
        # Convert to Philips Triple Net level for financial metrics
        tn_base  = t3n_base * K_BRIDGE
        tn_promo = tn_base * (1.0 - discounts)
        rev_base    = tn_base  * qty_base
        rev_promo   = tn_promo * qty_scn
        profit_base = (tn_base  - unit_cost) * qty_base
        profit_promo = (tn_promo - unit_cost) * qty_scn
        promo_spend = qty_scn * np.maximum(tn_base - tn_promo, 0.0)  # STTI
    else:
        tn_base  = t3n_base
        tn_promo = t3n_scn
        rev_base    = t3n_base * qty_base
        rev_promo   = t3n_scn  * qty_scn
        profit_base = (t3n_base - unit_cost) * qty_base
        profit_promo = (t3n_scn  - unit_cost) * qty_scn
        promo_spend = qty_scn * np.maximum(t3n_base - t3n_scn, 0.0)

    df = pd.DataFrame({
        "week":             df_sku["Week"].values,
        "discount":         discounts,
        "display_discount": (
            df_sku["display_discount"].values
            if "display_discount" in df_sku.columns
            else np.round(discounts * 10) / 10),
        "net_price_base":   tn_base,
        "net_price_promo":  tn_promo,
        "qty_base":         qty_base,
        "qty_promo":        qty_scn,
        "qty_actual":       qty_actual,
        "rev_base":         rev_base,
        "rev_promo":        rev_promo,
        "profit_base":      profit_base,
        "profit_promo":     profit_promo,
        "promo_spend":      promo_spend,
    })
    money_cols = [c for c in df.columns if c not in ("week", "discount")]
    df[money_cols] = df[money_cols].round(2)
    return df


# ─────────────────────────────────────────────────────────────────────
# 7. PORTFOLIO OPTIMIZER
# ─────────────────────────────────────────────────────────────────────
# PEAK_WEEK_PRIORITY = {
#     frozenset([45, 46, 47, 48]): 1.40,
#     frozenset([43, 44]): 1.20,
#     frozenset([49, 50, 51]): 1.35,
#     frozenset([52]): 1.15,
#     frozenset([1, 2, 3]): 1.10,
#     frozenset([26, 27, 28]): 1.08,
#     frozenset([22, 23, 24]): 1.05,
# }
PEAK_WEEK_PRIORITY = {
    frozenset([45, 46, 47, 48]): 1,
    frozenset([43, 44]): 1,
    frozenset([49, 50, 51]): 1,
    frozenset([52]): 1,
    frozenset([1, 2, 3]): 1,
    frozenset([26, 27, 28]): 1,
    frozenset([22, 23, 24]): 1,
}


def get_peak_multiplier(week: int) -> float:
    for week_set, multiplier in PEAK_WEEK_PRIORITY.items():
        if week in week_set:
            return multiplier
    return 1.0


def _score_single_sku_raw(
    sku: str,
    df_sku: pd.DataFrame,
    X: np.ndarray,
    W: np.ndarray,
    t3n_base: np.ndarray,
    qty_base: np.ndarray,
    unit_cost: float,
    discount_grid: np.ndarray,
    bounds_for_sku: tuple,
    economics: str = "legacy",
) -> list:
    # D1: per-quarter historical discount cap removed. The only depth guardrail is
    # the user's max_discount, already baked into discount_grid by the API. The
    # bounds_for_sku argument is retained for signature compatibility but no longer
    # constrains candidate depth.
    n_weeks          = len(df_sku)
    log_p_base       = np.log(t3n_base)
    log_q_base       = np.log(qty_base)
    profit_base_week = (t3n_base - unit_cost) * qty_base

    actual_price = (
        df_sku["Price"].values
        if "Price" in df_sku.columns
        else np.exp(df_sku["log_price"].values)
    )
    actual_discounts = np.clip(
        1.0 - actual_price / np.maximum(t3n_base, 1e-3),
        0.0, 0.99
    )

    candidates_per_week = []
    effective_max = float(discount_grid.max())
    for t in range(n_weeks):
        act_d = float(actual_discounts[t])
        cands = [(d, False) for d in discount_grid if 0.0 < d <= effective_max]
        if act_d > 0.005:
            cands.append((act_d, True))
        candidates_per_week.append(cands)

    week_indices  = []
    disc_values   = []
    is_actual_col = []
    for t, cands in enumerate(candidates_per_week):
        for d, is_act in cands:
            week_indices.append(t)
            disc_values.append(d)
            is_actual_col.append(is_act)

    if not week_indices:
        return []

    week_indices  = np.array(week_indices)
    disc_values   = np.array(disc_values)
    is_actual_col = np.array(is_actual_col)
    n_rows        = len(week_indices)

    X_batch         = X[week_indices]
    log_p0_batch    = log_p_base[week_indices]
    t3n_promo_batch = np.maximum(t3n_base[week_indices] * (1.0 - disc_values), 1e-3)
    log_p1_batch    = np.log(t3n_promo_batch)
    log_q0_batch    = log_q_base[week_indices]

    delta_batch = est_price_f.effect(
        X=X_batch,
        T0=log_p0_batch,
        T1=log_p1_batch,
    )
    delta_batch     = np.clip(delta_batch.ravel(), *DELTA_CLIP)
    qty_promo_batch = np.exp(log_q0_batch + delta_batch)

    # Financial metrics: in TN mode, convert to Philips Triple Net level.
    # EconML output (qty_promo_batch) is unchanged — model always runs on sell-out.
    if economics == "tn":
        fin_base_batch  = t3n_base[week_indices] * K_BRIDGE   # TN at list
        fin_promo_batch = fin_base_batch * (1.0 - disc_values)  # TN during promo
        fin_base_all    = t3n_base * K_BRIDGE
        profit_base_week_fin = (fin_base_all - unit_cost) * qty_base
    else:
        fin_base_batch  = t3n_base[week_indices]
        fin_promo_batch = t3n_promo_batch
        fin_base_all    = t3n_base
        profit_base_week_fin = profit_base_week

    profit_base_batch_fin = profit_base_week_fin[week_indices]
    raw_profit_gain_batch = (
        (fin_promo_batch - unit_cost) * qty_promo_batch - profit_base_batch_fin
    )

    weeks_batch       = df_sku["Week"].values[week_indices]
    multiplier_batch  = np.array([get_peak_multiplier(int(w)) for w in weeks_batch])
    promo_spend_batch = qty_promo_batch * np.maximum(fin_base_batch - fin_promo_batch, 0.0)
    week_num_batch    = df_sku["Week"].values[week_indices]

    records = []
    for i in range(n_rows):
        t       = int(week_indices[i])
        p_promo = float(fin_promo_batch[i])
        q_promo = float(qty_promo_batch[i])
        p_base  = float(fin_base_all[t])
        q_base  = float(qty_base[t])
        records.append({
            "sku":             sku,
            "week_idx":        t,
            "week":            int(week_num_batch[i]),
            "price_base":      p_base,
            "qty_base":        q_base,
            "discount":        float(disc_values[i]),
            "is_actual":       bool(is_actual_col[i]),
            "price_promo":     p_promo,
            "qty_promo":       q_promo,
            "profit_gain":     float(raw_profit_gain_batch[i]),
            "profit_gain_raw": float(raw_profit_gain_batch[i]),
            "promo_spend":     float(promo_spend_batch[i]),
            "peak_multiplier": float(multiplier_batch[i]),
            "rev_gain":        p_promo * q_promo - p_base * q_base,
            "qty_gain":        q_promo - q_base,
            "margin_pct":      (p_promo - unit_cost) / max(p_promo, 1e-3) * 100,
        })
    return records


def compute_cell_scores(
    sku_inputs: dict,
    discount_grid: np.ndarray,
    est,
    discount_bounds: dict = None,
    economics: str = "legacy",
) -> pd.DataFrame:
    records = []
    skus    = list(sku_inputs.keys())
    for idx, (sku, (df_sku, X, W, t3n_base, qty_base, unit_cost)) in enumerate(sku_inputs.items()):

        bounds_for_sku = tuple(
            (q, float(discount_bounds[(sku, q)][0])
             if discount_bounds and (sku, q) in discount_bounds
             else float(discount_grid.max()))
            for q in QUARTER_WEEKS
        )

        sku_records = _score_single_sku_raw(
            sku, df_sku, X, W, t3n_base, qty_base, unit_cost,
            discount_grid, bounds_for_sku, economics=economics,
        )
        records.extend(sku_records)


    df_out = pd.DataFrame(records)
    if df_out.empty:
        return df_out

    sku_median_pos = (
        df_out[df_out["profit_gain_raw"] > 0]
        .groupby("sku")["profit_gain_raw"]
        .median()
    )
    portfolio_median_pos = float(
        df_out.loc[df_out["profit_gain_raw"] > 0, "profit_gain_raw"].median()
    ) if (df_out["profit_gain_raw"] > 0).any() else 0.0

    df_out["_sku_median_pos"] = (
        df_out["sku"].map(sku_median_pos).fillna(portfolio_median_pos)
    )
    bonus = (df_out["peak_multiplier"] - 1.0) * df_out["_sku_median_pos"]
    df_out["profit_gain"] = df_out["profit_gain_raw"] + np.where(
        df_out["peak_multiplier"] > 1.0, bonus, 0.0
    )
    df_out.drop(columns=["_sku_median_pos"], inplace=True)
    return df_out


ALL_PEAK_HALO_WEEKS = frozenset(w for week_set in PEAK_WEEK_PRIORITY for w in week_set)


def _build_campaign_windows() -> list:
    sorted_weeks = sorted(ALL_PEAK_HALO_WEEKS)
    if not sorted_weeks:
        return []
    campaigns, start, prev = [], sorted_weeks[0], sorted_weeks[0]
    for w in sorted_weeks[1:]:
        if w - prev <= 2:
            prev = w
        else:
            campaigns.append((start, prev))
            start = prev = w
    campaigns.append((start, prev))
    return campaigns


CAMPAIGN_WINDOWS = _build_campaign_windows()


def _get_campaign(week: int):
    for start, end in CAMPAIGN_WINDOWS:
        if start <= week <= end:
            return (start, end)
    return None


def enforce_calendar_rules(
    assigned: dict,
    cell_scores: pd.DataFrame,
    max_campaign_streak: int = 6,
    min_offpeak_gap: int = 3,
) -> dict:
    if not assigned or cell_scores is None or cell_scores.empty:
        return assigned

    score_col = "profit_gain_raw" if "profit_gain_raw" in cell_scores.columns else "profit_gain"

    gain_lookup = {}
    for _, row in cell_scores[cell_scores["profit_gain"] > 0].iterrows():
        key = (row["sku"], int(row["week_idx"]))
        if key in assigned and abs(assigned[key] - row["discount"]) < 0.005:
            gain_lookup[key] = float(row[score_col])

    week_map = {}
    for _, row in cell_scores.drop_duplicates(subset=["sku", "week_idx"]).iterrows():
        week_map[(row["sku"], int(row["week_idx"]))] = int(row["week"])

    sku_weeks = defaultdict(list)
    for (sku, week_idx), disc in assigned.items():
        actual_week = week_map.get((sku, week_idx), -1)
        sku_weeks[sku].append({
            "week_idx": week_idx,
            "disc": disc,
            "actual_week": actual_week,
            "gain": gain_lookup.get((sku, week_idx), 0.0),
            "campaign": _get_campaign(actual_week),
        })

    cleaned = {}

    for sku, entries in sku_weeks.items():
        entries.sort(key=lambda x: x["actual_week"])

        campaign_entries = [e for e in entries if e["campaign"] is not None]
        offpeak_entries = [e for e in entries if e["campaign"] is None]

        by_campaign = defaultdict(list)
        for e in campaign_entries:
            by_campaign[e["campaign"]].append(e)

        for campaign, camp_entries in by_campaign.items():
            camp_entries.sort(key=lambda x: x["actual_week"])
            if len(camp_entries) <= max_campaign_streak:
                for e in camp_entries:
                    cleaned[(sku, e["week_idx"])] = e["disc"]
            else:
                top = sorted(camp_entries, key=lambda x: x["gain"],
                             reverse=True)[:max_campaign_streak]
                for e in top:
                    cleaned[(sku, e["week_idx"])] = e["disc"]

        if not offpeak_entries:
            continue

        kept_offpeak = []
        for e in offpeak_entries:
            if not kept_offpeak:
                kept_offpeak.append(e)
            else:
                last = kept_offpeak[-1]
                gap = e["actual_week"] - last["actual_week"]
                if gap >= min_offpeak_gap:
                    kept_offpeak.append(e)
                else:
                    if e["gain"] > last["gain"]:
                        kept_offpeak[-1] = e

        for e in kept_offpeak:
            cleaned[(sku, e["week_idx"])] = e["disc"]

    return cleaned


_MANDATORY_CAMPAIGN_WEEKS = frozenset(range(43, 52))  # market default; meta.mandatory_campaign_weeks overrides


def enforce_mandatory_peak_inclusion(
    assigned: dict,
    cell_scores: pd.DataFrame,
    mandatory_weeks: frozenset | None = None,
) -> tuple:
    # Resolved at call time: a default argument would freeze the CZ weeks at
    # import, before the artifact's meta block has been read.
    if mandatory_weeks is None:
        mandatory_weeks = _MANDATORY_CAMPAIGN_WEEKS
    if cell_scores is None or cell_scores.empty:
        return assigned, {}

    week_map = {}
    for _, row in cell_scores.drop_duplicates(subset=["sku", "week_idx"]).iterrows():
        week_map[(row["sku"], int(row["week_idx"]))] = int(row["week"])

    assigned_mandatory_skus = set()
    for (sku, week_idx), disc in assigned.items():
        actual_week = week_map.get((sku, week_idx), -1)
        if actual_week in mandatory_weeks:
            assigned_mandatory_skus.add(sku)

    all_skus = cell_scores["sku"].unique()
    forced_cost = {}

    for sku in all_skus:
        if sku in assigned_mandatory_skus:
            continue
        cands = cell_scores[
            (cell_scores["sku"] == sku) &
            (cell_scores["week"].isin(mandatory_weeks))
        ]
        if cands.empty:
            continue
        best_idx = (
            cands
            .sort_values(["profit_gain_raw", "discount"], ascending=[False, True])
            .index[0]
        )
        best_row = cands.loc[best_idx]
        key = (sku, int(best_row["week_idx"]))
        assigned[key] = float(best_row["discount"])
        forced_cost[sku] = float(best_row["profit_gain_raw"])

    return assigned, forced_cost


_DP_TARGET_BINS = 5_000


def _dp_core(pos: pd.DataFrame, B: int, budget_bin: int) -> dict:
    groups = []
    for (sku, week_idx), grp in pos.groupby(["sku", "week_idx"]):
        options = []
        for _, row in grp.iterrows():
            spend_bins = max(1, int(round(row["promo_spend"] / budget_bin)))
            if spend_bins <= B:
                options.append((
                    int(round(row["_value"])),
                    spend_bins,
                    row["discount"],
                ))
        if options:
            groups.append(((sku, week_idx), options))

    assigned = {}
    if not groups:
        return assigned

    G = len(groups)
    NEG = np.int64(-(10 ** 15))

    dp = np.full(B + 1, NEG, dtype=np.int64)
    dp[0] = 0
    track_oi = np.full((G, B + 1), -2, dtype=np.int16)
    track_bp = np.full((G, B + 1), -1, dtype=np.int32)

    for gi, ((sku, week_idx), options) in enumerate(groups):
        new_dp = dp.copy()

        reachable = dp != NEG
        r_idx = np.where(reachable)[0]
        track_oi[gi, r_idx] = -1
        track_bp[gi, r_idx] = r_idx

        for oi, (gain, spend_bins, _) in enumerate(options):
            if spend_bins > B:
                continue
            src = dp[:B + 1 - spend_bins]
            valid = src != NEG
            cand = np.where(valid, src + gain, NEG)
            target = new_dp[spend_bins:]
            improve = cand > target
            new_dp[spend_bins:] = np.where(improve, cand, target)
            b_new_idx = np.where(improve)[0] + spend_bins
            b_prev_idx = b_new_idx - spend_bins
            track_oi[gi, b_new_idx] = oi
            track_bp[gi, b_new_idx] = b_prev_idx

        dp = new_dp

    best_b = int(np.argmax(dp))
    b = best_b
    for gi in range(G - 1, -1, -1):
        (sku, week_idx), options = groups[gi]
        oi = int(track_oi[gi, b])
        if oi >= 0:
            assigned[(sku, week_idx)] = options[oi][2]
        if track_bp[gi, b] >= 0:
            b = int(track_bp[gi, b])
    return assigned


def _run_dp_for_budget(pos: pd.DataFrame, budget_cap: float, budget_bin: int) -> dict:
    if pos is None or pos.empty or budget_cap <= 0:
        return {}
    B = max(1, int(budget_cap // budget_bin))
    if B > _DP_TARGET_BINS:
        budget_bin = max(budget_bin, int(budget_cap / _DP_TARGET_BINS))
        B = max(1, int(budget_cap // budget_bin))
    return _dp_core(pos, B, budget_bin)


def portfolio_knapsack_dp(
    cell_scores: pd.DataFrame,
    budget_cap: float,
    budget_bin: int = 100,
    max_campaign_streak: int = 5,
    min_offpeak_gap: int = 3,
    enforce_peak_inclusion: bool = True,
    alpha: float = 1.0,
    margin_floor: float = 0.0,
    quarter_budgets: dict = None,
) -> tuple:
    if cell_scores is None or cell_scores.empty:
        return {}, {}

    cs = cell_scores.copy()
    cs["_value"] = alpha * cs["profit_gain"] + (1.0 - alpha) * cs["rev_gain"]

    if margin_floor and margin_floor > 0:
        cs = cs[cs["margin_pct"] >= margin_floor]

    pos = cs[cs["_value"] > 0].copy()

    if budget_cap == float("inf"):
        assigned = {}
        for (sku, week_idx), grp in pos.groupby(["sku", "week_idx"]):
            best_row = grp.loc[grp["_value"].idxmax()]
            assigned[(sku, int(week_idx))] = best_row["discount"]
    elif quarter_budgets:
        assigned = {}
        pos_q = pos.copy()
        pos_q["_quarter"] = pos_q["week"].apply(get_quarter_for_week)
        for q, q_cap in quarter_budgets.items():
            sub = pos_q[pos_q["_quarter"] == q]
            assigned.update(_run_dp_for_budget(sub, float(q_cap), budget_bin))
    else:
        assigned = _run_dp_for_budget(pos, budget_cap, budget_bin)

    assigned = enforce_calendar_rules(
        assigned, cell_scores,
        max_campaign_streak=max_campaign_streak,
        min_offpeak_gap=min_offpeak_gap,
    )
    if enforce_peak_inclusion:
        assigned, forced_cost = enforce_mandatory_peak_inclusion(assigned, cell_scores)
    else:
        forced_cost = {}
    return assigned, forced_cost


# ─────────────────────────────────────────────────────────────────────
# 8. HIGH-LEVEL PIPELINE
# ─────────────────────────────────────────────────────────────────────
def prepare_sku_inputs(
    skus: list,
    start_year: int, start_week: int,
    n_weeks: int = None,
    end_year: int = None, end_week: int = None,
    economics: str = "legacy",
) -> dict:
    result = {}
    for sku in skus:
        df = get_sku_slice(sku, start_year, start_week,
                           n_weeks=n_weeks, end_year=end_year, end_week=end_week)
        if df.empty or df[["log_price_base", "log_qty_base"]].isna().any().any():
            continue
        try:
            cogs = get_cogs(sku)
        except ValueError:
            continue
        t3n_base  = df["Price_base"].values if "Price_base" in df.columns else np.exp(df["log_price_base"].values)
        qty_base  = df["Qty_base"].values if "Qty_base" in df.columns else np.exp(df["log_qty_base"].values)
        unit_cost = derive_unit_cost(t3n_base, cogs, economics=economics)
        X, W      = build_X_W(df)
        result[sku] = (df, X, W, t3n_base, qty_base, unit_cost)
    return result


def _category_avg_qty_by_week(band: str, year: int) -> dict:
    """Average ``Qty_base`` per week across all SKUs in the same price band
    (``Classification``) for ``year``. Gives a mid-year SKU a seasonally
    sensible pre-launch quantity shape (Decision 7) — January looks like
    January, not like the launch week."""
    sub = panel_df[(panel_df["Classification"] == band) & (panel_df["Year"] == year)]
    if sub.empty:
        return {}
    qty = (
        sub["Qty_base"].values
        if "Qty_base" in sub.columns
        else np.exp(sub["log_qty_base"].values)
    )
    s = pd.Series(qty, index=sub["Week"].values.astype(int))
    return s.groupby(level=0).mean().to_dict()


def build_forecast_sku_inputs(
    skus: list,
    base_year: int | None = None,
    use_trend: bool = True,
    economics: str = "legacy",
) -> dict:
    def _week_qty_map(sku: str, year: int) -> dict:
        d = get_sku_slice(sku, year, 1, end_year=year, end_week=WEEKS_PER_YEAR)
        if d.empty:
            return {}
        qty = (
            d["Qty_base"].values
            if "Qty_base" in d.columns
            else np.exp(d["log_qty_base"].values)
        )
        return dict(zip(d["Week"].values.astype(int), qty))

    result = {}
    for sku in skus:
        df_base = get_sku_slice(sku, base_year, 1, end_year=base_year, end_week=WEEKS_PER_YEAR)
        if df_base.empty or df_base[["log_price_base", "log_qty_base"]].isna().any().any():
            continue

        df_base["is_prelaunch"] = False

        # Mid-year SKU: launched partway through base_year — a short year.
        # (Decision 7) Project the missing early weeks with the price band's seasonal
        # quantity shape instead of flat-padding the launch week, so January looks
        # like January rather than like the (atypical) launch week.
        #
        # IMPORTANT: pad rows REUSE the launch week's original panel index. build_X_W
        # resolves features via `_X_full.loc[df.index]`, so a reset_index here would
        # silently map every week of this SKU to the wrong panel rows. Keeping the
        # launch index makes pre-launch weeks borrow the launch week's causal features
        # (we have no observed features for those weeks) while post-launch weeks keep
        # their own.
        if len(df_base) < WEEKS_PER_YEAR:
            first_week = int(df_base["Week"].min())
            if first_week > 1:
                launch_row  = df_base.iloc[[0]]          # original panel index kept
                launch_qty  = (
                    float(launch_row["Qty_base"].iloc[0])
                    if "Qty_base" in launch_row.columns
                    else float(np.exp(launch_row["log_qty_base"].iloc[0]))
                )
                band        = str(df_base["Classification"].iloc[0])
                cat_avg     = _category_avg_qty_by_week(band, base_year)
                cat_launch  = float(cat_avg.get(first_week, 0.0))

                pad_rows = []
                for w in range(1, first_week):
                    r       = launch_row.copy()          # keeps launch index label
                    cat_w   = float(cat_avg.get(w, 0.0))
                    proj_qty = (
                        launch_qty * cat_w / cat_launch
                        if cat_launch > 1e-3 and cat_w > 1e-3
                        else launch_qty
                    )
                    r["Week"]         = w
                    r["is_prelaunch"] = True
                    if "Qty_base" in r.columns:
                        r["Qty_base"] = proj_qty
                    r["log_qty_base"] = float(np.log(max(proj_qty, 1e-3)))
                    pad_rows.append(r)

                # No reset_index: pad rows intentionally share the launch index so the
                # feature lookup in build_X_W stays correct.
                df_base = pd.concat([*pad_rows, df_base]).sort_values("Week")

        t3n_base = (
            df_base["Price_base"].values
            if "Price_base" in df_base.columns
            else np.exp(df_base["log_price_base"].values)
        )
        qty_base_by = (
            df_base["Qty_base"].values
            if "Qty_base" in df_base.columns
            else np.exp(df_base["log_qty_base"].values)
        )

        growth = np.ones(len(df_base))
        if use_trend:
            q_cur   = dict(zip(df_base["Week"].values.astype(int), qty_base_by))
            q_prev  = _week_qty_map(sku, base_year - 1)
            q_prev2 = _week_qty_map(sku, base_year - 2)

            factors = []
            for w, q_by in zip(df_base["Week"].values.astype(int), qty_base_by):
                ratios = []
                if w in q_prev and q_prev[w] > 1e-3:
                    ratios.append(q_by / q_prev[w])
                if w in q_prev and w in q_prev2 and q_prev2[w] > 1e-3:
                    ratios.append(q_prev[w] / q_prev2[w])
                if ratios:
                    g = float(np.exp(np.mean(np.log(np.clip(ratios, 0.5, 1.5)))))
                    factors.append(g)
                else:
                    factors.append(1.0)
            growth = np.array(factors)

        qty_base_proj = qty_base_by * growth

        try:
            cogs = get_cogs(sku)
        except ValueError:
            continue

        unit_cost = derive_unit_cost(t3n_base, cogs, economics=economics)
        X, W      = build_X_W(df_base)
        result[sku] = (df_base, X, W, t3n_base, qty_base_proj, unit_cost)

    return result


def run_portfolio(
    sku_inputs: dict,
    discount_grid: np.ndarray,
    budget_cap: float,
    est,
    max_campaign_streak: int = 5,
    min_offpeak_gap:  int = 3,
    discount_bounds: dict = None,
    alpha: float = 1.0,
    margin_floor: float = 0.0,
    quarter_budgets: dict = None,
    economics: str = "legacy",
) -> tuple:
    # Calendar looseness keys off alpha (Decision 6, threshold-on-alpha): a
    # revenue-leaning blend (alpha < 0.5) allows longer streaks / shorter gaps so
    # high-frequency promo SKUs can still hit recommended >= actual, while a
    # profit-leaning blend keeps the tighter 5/3 calendar. This preserves the old
    # profit (5/3) and turnover (8/2) behavior at the alpha=1 / alpha=0 extremes.
    if alpha < 0.5:
        max_campaign_streak = 8
        min_offpeak_gap     = 2

    base_results = {}
    for sku, (df_sku, X, W, t3n_base, qty_base, unit_cost) in sku_inputs.items():
        base_results[sku] = simulate_scenario(
            est=est, discounts=np.zeros(len(df_sku)),
            unit_cost=unit_cost, df_sku=df_sku,
            X=X, W=W, t3n_base=t3n_base, qty_base=qty_base,
            economics=economics,
        )

    cell_scores = compute_cell_scores(sku_inputs, discount_grid, est,
                                      discount_bounds=discount_bounds,
                                      economics=economics)
    assigned, forced_cost = portfolio_knapsack_dp(
        cell_scores, budget_cap,
        max_campaign_streak=max_campaign_streak,
        min_offpeak_gap=min_offpeak_gap,
        alpha=alpha,
        margin_floor=margin_floor,
        quarter_budgets=quarter_budgets,
    )

    opt_results = {}
    for sku, (df_sku, X, W, t3n_base, qty_base, unit_cost) in sku_inputs.items():
        n = len(df_sku)
        opt_disc = np.array([assigned.get((sku, t), 0.0) for t in range(n)])
        opt_results[sku] = simulate_scenario(
            est=est, discounts=opt_disc,
            unit_cost=unit_cost, df_sku=df_sku,
            X=X, W=W, t3n_base=t3n_base, qty_base=qty_base,
            economics=economics,
        )

    return base_results, opt_results, cell_scores, forced_cost


def aggregate_portfolio(results_by_sku: dict) -> pd.DataFrame:
    if not results_by_sku:
        return pd.DataFrame()
    combined = pd.concat(
        [df.assign(SKU=sku) for sku, df in results_by_sku.items()],
        ignore_index=True,
    )
    return combined.groupby("week", as_index=False).agg({
        "qty_promo": "sum",
        "rev_promo": "sum",
        "profit_promo": "sum",
        "promo_spend": "sum",
        "discount": "mean",
    })


# ─────────────────────────────────────────────────────────────────────
# 9. BUDGET HELPERS
# ─────────────────────────────────────────────────────────────────────
def compute_reference_spend(skus: tuple, ref_year: int, economics: str = "legacy") -> float:
    total = 0.0
    for sku in skus:
        df = panel_df[
            (panel_df["SKU"] == sku) & (panel_df["Year"] == ref_year)
        ]
        if df.empty:
            continue
        if not {"log_price", "log_qty", "log_price_base"}.issubset(df.columns):
            continue
        real_price = df["Price"].values if "Price" in df.columns else np.exp(df["log_price"].values)
        base_price = df["Price_base"].values if "Price_base" in df.columns else np.exp(df["log_price_base"].values)
        real_qty   = df["Qty"].values if "Qty" in df.columns else np.exp(df["log_qty"].values)
        if economics == "tn":
            # STTI = qty × TN_base × discount;  discount = (base - real) / base
            tn_base = base_price * K_BRIDGE
            tn_real = real_price * K_BRIDGE
            total += (real_qty * np.maximum(tn_base - tn_real, 0.0)).sum()
        else:
            total += (real_qty * np.maximum(base_price - real_price, 0.0)).sum()
    return total


def compute_period_spend(skus: tuple, start_year: int, start_week: int,
                         end_year: int, end_week: int, economics: str = "legacy") -> float:
    total     = 0.0
    start_key = start_year * 100 + start_week
    end_key   = end_year   * 100 + end_week
    for sku in skus:
        df = panel_df[panel_df["SKU"] == sku].copy()
        df["yw"] = df["Year"] * 100 + df["Week"]
        df = df[(df["yw"] >= start_key) & (df["yw"] <= end_key)]
        if df.empty:
            continue
        if not {"log_price", "log_qty", "log_price_base"}.issubset(df.columns):
            continue
        real_price = df["Price"].values if "Price" in df.columns else np.exp(df["log_price"].values)
        base_price = df["Price_base"].values if "Price_base" in df.columns else np.exp(df["log_price_base"].values)
        real_qty   = df["Qty"].values if "Qty" in df.columns else np.exp(df["log_qty"].values)
        if economics == "tn":
            tn_base = base_price * K_BRIDGE
            tn_real = real_price * K_BRIDGE
            total += (real_qty * np.maximum(tn_base - tn_real, 0.0)).sum()
        else:
            total += (real_qty * np.maximum(base_price - real_price, 0.0)).sum()
    return total


def compute_sku_quarterly_discount_bounds(skus: tuple) -> dict:
    bounds = {}
    for sku in skus:
        df = panel_df[panel_df["SKU"] == sku].copy()
        if df.empty:
            for q in QUARTER_WEEKS:
                bounds[(sku, q)] = (0.40, None)
            continue

        if "Price" in df.columns and "Price_base" in df.columns:
            df["_disc"] = np.clip(
                1.0 - df["Price"] / np.maximum(df["Price_base"], 1e-3),
                0.0, 0.45,
            )
        elif "log_price" in df.columns and "log_price_base" in df.columns:
            df["_disc"] = np.clip(
                1.0 - np.exp(df["log_price"]) / np.exp(df["log_price_base"].clip(lower=-10)),
                0.0, 0.45,
            )
        else:
            for q in QUARTER_WEEKS:
                bounds[(sku, q)] = (0.40, None)
            continue

        for q, (w_start, w_end) in QUARTER_WEEKS.items():
            q_df = df[(df["Week"] >= w_start) & (df["Week"] <= w_end)]
            promo_df = q_df[q_df["_disc"] > 0.01]
            if promo_df.empty:
                bounds[(sku, q)] = (0.25, None)
            else:
                idx = promo_df["_disc"].idxmax()
                max_disc = float(promo_df.loc[idx, "_disc"])
                year = int(promo_df.loc[idx, "Year"]) if "Year" in promo_df.columns else None
                bounds[(sku, q)] = (max_disc, year)

    return bounds


# ─────────────────────────────────────────────────────────────────────
# 10. SYNTHESIS HELPERS
# ─────────────────────────────────────────────────────────────────────
def _confidence_tier(gain: float, p25: float, p75: float) -> str:
    if gain >= p75:
        return "Definitely do"
    elif gain >= p25:
        return "Worth considering"
    else:
        return "Minor impact"


def _add_confidence_tiers(cell_scores: pd.DataFrame, sku_rows: list) -> list:
    if cell_scores is None or cell_scores.empty:
        for r in sku_rows:
            r["Confidence"] = "—"
        return sku_rows

    pos_gains = cell_scores.loc[cell_scores["profit_gain"] > 0, "profit_gain"]
    if pos_gains.empty:
        for r in sku_rows:
            r["Confidence"] = "—"
        return sku_rows

    p25 = float(pos_gains.quantile(0.25))
    p75 = float(pos_gains.quantile(0.75))
    sku_median = (
        cell_scores[cell_scores["profit_gain"] > 0]
        .groupby("sku")["profit_gain"]
        .median()
    )
    for r in sku_rows:
        sku  = r.get("SKU", "")
        gain = float(sku_median.get(sku, 0.0))
        r["Confidence"] = _confidence_tier(gain, p25, p75)
    return sku_rows


def _diagnose_q4_allocation(opt_results: dict) -> str | None:
    q_spend = {}
    for q, (w_start, w_end) in QUARTER_WEEKS.items():
        total = sum(
            opt_results[sku].loc[
                opt_results[sku]["week"].between(w_start, w_end), "promo_spend"
            ].sum()
            for sku in opt_results
        )
        q_spend[q] = total

    total_spend = sum(q_spend.values())
    if total_spend < 1:
        return None

    q4_share  = q_spend.get("Q4", 0.0) / total_spend
    other_avg = (total_spend - q_spend.get("Q4", 0.0)) / max(total_spend, 1) / 3

    if q4_share < 0.15 and q_spend.get("Q4", 0.0) < other_avg * total_spend * 0.6:
        q4_weeks = sum(
            int((opt_results[sku]["week"].between(40, WEEKS_PER_YEAR) & (opt_results[sku]["discount"] > 0)).sum())
            for sku in opt_results
        )
        campaign_wks = sorted(_MANDATORY_CAMPAIGN_WEEKS)
        campaign_range = f"wks {campaign_wks[0]}–{campaign_wks[-1]}" if campaign_wks else "mandatory campaign weeks"
        event_labels = [ef["label"] for ef in EVENT_FLAGS[:3]] if EVENT_FLAGS else ["key events"]
        event_str = " / ".join(event_labels)
        return (
            f"**Why does Q4 have fewer recommended promos?**  \n"
            f"Q4 receives **{q4_share*100:.0f}% of the budget** in this plan "
            f"({q4_weeks} promo-weeks across all SKUs). This happens when the model "
            f"estimates that peak-season demand is already strong enough that discounting "
            f"adds less incremental volume than in softer quarters — i.e. you are "
            f"giving away margin on sales you would have made anyway. "
            f"The {event_str} campaign ({campaign_range}) is always included "
            f"for commercial visibility, but deeper or wider discounting in Q4 "
            f"scored lower than the same budget deployed in Q1–Q3. "
            f"If a higher Q4 floor is commercially required, use the "
            f"**Min. budget per quarter** slider to force a minimum allocation."
        )
    return None


def get_tier_cells(cell_scores: pd.DataFrame) -> dict:
    """Return {tier_name: [row, ...]} for best cells per (sku, week) bucketed by tier."""
    # Resolved from the artifact when the caller does not say.
    if base_year is None:
        years = history_years()
        base_year = max(years) if years else int(panel_df["Year"].max())
    if cell_scores is None or cell_scores.empty:
        return {"Definitely do": [], "Worth considering": [], "Minor impact": []}

    pos = cell_scores[cell_scores["profit_gain"] > 0]
    if pos.empty:
        return {"Definitely do": [], "Worth considering": [], "Minor impact": []}

    p25 = float(pos["profit_gain"].quantile(0.25))
    p75 = float(pos["profit_gain"].quantile(0.75))

    best = (
        pos.sort_values("profit_gain", ascending=False)
        .drop_duplicates(subset=["sku", "week"])
    )

    tiers: dict = {"Definitely do": [], "Worth considering": [], "Minor impact": []}
    for _, row in best.iterrows():
        t = _confidence_tier(float(row["profit_gain"]), p25, p75)
        tiers[t].append(row)
    return tiers