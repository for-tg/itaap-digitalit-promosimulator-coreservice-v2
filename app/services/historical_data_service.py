"""
Historical data service.

Calculates historical revenue, profit, promotional spend, ROI,
incremental units, SKU summaries, and weekly trends using the same
Triple Net economics used by the Promo Simulator optimization flow.
"""

import logging
from typing import Any

import numpy as np
import pandas as pd
from fastapi import HTTPException, status

from app.engine import promo_engine


logger = logging.getLogger(__name__)


def _valid_classifications() -> set:
    """The loaded market's price bands, from meta.segment_labels."""
    return set(promo_engine.PRICE_BANDS)


def _validate_required_columns(
    dataframe: pd.DataFrame,
) -> None:
    """Validate columns required for historical calculations."""

    required_columns = {
        "SKU",
        "Year",
        "Week",
        "Classification",
        "Price",
        "Qty",
        "Price_base",
        "Qty_base",
    }

    missing_columns = (
        required_columns
        - set(dataframe.columns)
    )

    if missing_columns:
        missing_columns_text = ", ".join(
            sorted(missing_columns)
        )

        raise RuntimeError(
            "Historical data is missing required columns: "
            f"{missing_columns_text}"
        )


def _process_historical_data(
    historical_df: pd.DataFrame,
    economics: str = "tn",
) -> dict[str, Any]:
    """Calculate historical KPIs and SKU trends."""

    sku_summary: list[dict[str, Any]] = []
    weekly_trends: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    for sku, sku_df in historical_df.groupby("SKU"):
        sku_df = (
            sku_df
            .sort_values("Week")
            .copy()
        )

        required_numeric_columns = [
            "Price",
            "Qty",
            "Price_base",
            "Qty_base",
        ]

        for column in required_numeric_columns:
            sku_df[column] = pd.to_numeric(
                sku_df[column],
                errors="coerce",
            )

        sku_df = sku_df.dropna(
            subset=required_numeric_columns,
        )

        if sku_df.empty:
            continue

        try:
            cogs = promo_engine.get_cogs(
                str(sku)
            )

        except ValueError:
            logger.warning(
                "Skipping SKU %s because COGS is unavailable.",
                sku,
            )
            continue

        sell_out_base = (
            sku_df["Price_base"]
            .to_numpy(dtype=float)
        )

        sell_out_actual = (
            sku_df["Price"]
            .to_numpy(dtype=float)
        )

        qty_base = (
            sku_df["Qty_base"]
            .to_numpy(dtype=float)
        )

        qty_actual = (
            sku_df["Qty"]
            .to_numpy(dtype=float)
        )

        # ------------------------------------------------------------------
        # Triple Net economics
        # ------------------------------------------------------------------
        # ------------------------------------------------------------------
        # Price reference / economics
        # ------------------------------------------------------------------

        if economics == "tn":
            financial_base = (
                sell_out_base
                * promo_engine.K_BRIDGE
            )

            financial_actual = (
                sell_out_actual
                * promo_engine.K_BRIDGE
            )

            unit_cost = (
                float(cogs)
                + (
                    promo_engine.CONTRIB_COST_RATE
                    * float(financial_base.mean())
                )
            )

        else:
            financial_base = sell_out_base
            financial_actual = sell_out_actual

            unit_cost = (
                float(cogs)
                + (
                    promo_engine.LEGACY_TRADE_COST_RATE
                    * float(financial_base.mean())
                )
            )

        # ------------------------------------------------------------------
        # Historical actual metrics
        # ------------------------------------------------------------------

        revenue = (
            financial_actual
            * qty_actual
        )

        profit = (
            (
                financial_actual
                - unit_cost
            )
            * qty_actual
        )

        promo_spend = (
            qty_actual
            * np.maximum(
                financial_base
                - financial_actual,
                0.0,
            )
        )

        # ------------------------------------------------------------------
        # No-promo/base comparison
        # ------------------------------------------------------------------

        base_profit = (
            (
                financial_base
                - unit_cost
            )
            * qty_base
        )
        

        incremental_profit = (
            profit
            - base_profit
        )

        incremental_units = (
            qty_actual
            - qty_base
        )

        return_per_kc = np.divide(
            incremental_profit, promo_spend,
            out=np.zeros_like(incremental_profit, dtype=float),
            where=promo_spend > 1,
        )

        # ------------------------------------------------------------------
        # Satyam feedback (2026-09-08): heat map hover needs discount depth,
        # and "Promo Effectiveness" (traditional ROI = incremental revenue /
        # spend) needs a no-promo revenue baseline to compare against.
        # ------------------------------------------------------------------

        discount = np.divide(
            sell_out_base - sell_out_actual, sell_out_base,
            out=np.zeros_like(sell_out_base, dtype=float),
            where=sell_out_base > 0,
        )
        discount = np.maximum(discount, 0.0)

        base_revenue = (
            financial_base
            * qty_base
        )

        # IGM = (TN_price - COGS) × qty  — COGS only, no TPW/OFSE component.
        # Differs from `profit` (which includes TPW+OFSE in unit_cost) by
        # CONTRIB_COST_RATE × mean(TN_base) × qty.  Stakeholder definition:
        # IGM = ASP − VAT − PPWF (excl. STTI) − COGS.  (2026-09-16)
        igm = (financial_actual - float(cogs)) * qty_actual
        base_igm = (financial_base - float(cogs)) * qty_base

        weekly_df = pd.DataFrame(
            {
                "Week": sku_df["Week"]
                .astype(int)
                .to_numpy(),
                "Revenue": revenue,
                "Profit": profit,
                "PromoSpend": promo_spend,
                "BaseProfit": base_profit,
                "BaseRevenue": base_revenue,
                "Incremental": incremental_profit,
                "IncrementalUnits": incremental_units,
                "QtyActual": qty_actual,
                "QtyBase": qty_base,
                "ReturnPerKc": return_per_kc,
                "Discount": discount,
                # Sell-out ASP per week — the actual consumer shelf price.
                # Satyam Units vs ASP chart (2026-09-17).
                "AvgPrice": sell_out_actual,
            }
        )

        weekly_df = (
            weekly_df
            .replace(
                [np.inf, -np.inf],
                0,
            )
            .fillna(0)
        )

        weekly_trends[str(sku)] = (
            weekly_df.to_dict(
                orient="records"
            )
        )

        spend_total = float(
            promo_spend.sum()
        )

        revenue_total = float(
            revenue.sum()
        )

        profit_total = float(
            profit.sum()
        )

        igm_total = float(igm.sum())
        base_igm_total = float(base_igm.sum())
        base_revenue_total = float(base_revenue.sum())

        incremental_total = float(
            incremental_profit.sum()
        )

        incremental_units_total = float(
            incremental_units.sum()
        )

        qty_actual_total = float(
            qty_actual.sum()
        )

        qty_base_total = float(
            qty_base.sum()
        )

        roi_total = (
            incremental_total
            / spend_total
            if spend_total > 1
            else 0.0
        )

        classification = str(
            sku_df[
                "Classification"
            ].iloc[0]
        )

        sku_summary.append(
            {
                "SKU": str(sku),
                "Classification": classification,
                "Spend": spend_total,
                "Revenue": revenue_total,
                "Profit": profit_total,
                "Igm": igm_total,
                "BaseIgm": base_igm_total,
                "BaseRevenue": base_revenue_total,
                "Incremental": incremental_total,
                "IncrementalUnits": (
                    incremental_units_total
                ),
                "QtyActual": qty_actual_total,
                "QtyBase": qty_base_total,
                "ReturnPerKc": float(
                    roi_total
                ),
            }
        )

    if not sku_summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No historical data was found for "
                "the selected filters."
            ),
        )

    sku_summary_df = (
        pd.DataFrame(
            sku_summary
        )
        .sort_values(
            by="Spend",
            ascending=False,
        )
    )

    total_spend = float(
        sku_summary_df[
            "Spend"
        ].sum()
    )

    total_revenue = float(
        sku_summary_df[
            "Revenue"
        ].sum()
    )

    total_profit = float(
        sku_summary_df[
            "Profit"
        ].sum()
    )

    total_igm = float(
        sku_summary_df["Igm"].sum()
    )

    total_base_igm = float(
        sku_summary_df["BaseIgm"].sum()
    )

    total_base_revenue = float(
        sku_summary_df["BaseRevenue"].sum()
    )

    total_incremental = float(
        sku_summary_df[
            "Incremental"
        ].sum()
    )

    total_incremental_units = float(
        sku_summary_df[
            "IncrementalUnits"
        ].sum()
    )

    total_qty_actual = float(
        sku_summary_df[
            "QtyActual"
        ].sum()
    )

    total_qty_base = float(
        sku_summary_df[
            "QtyBase"
        ].sum()
    )

    portfolio_return = (
        total_incremental
        / total_spend
        if total_spend > 1
        else 0.0
    )

    volume_factor = (
        total_qty_actual
        / total_qty_base
        if total_qty_base > 0
        else 1.0
    )

    negative_skus = int(
        (
            sku_summary_df[
                "Incremental"
            ]
            < 0
        ).sum()
    )

    igm_margin_pct = (
        total_igm / total_revenue * 100
        if total_revenue > 0
        else 0.0
    )

    promo_effectiveness = (
        (total_revenue - total_base_revenue) / total_spend
        if total_spend > 1
        else 0.0
    )

    kpis = {
        "Revenue": total_revenue,
        "Profit": total_profit,
        "Igm": total_igm,
        "IgmMarginPct": round(igm_margin_pct, 1),
        "BaseIgm": total_base_igm,
        "BaseIgmMarginPct": round(
            total_base_igm / total_base_revenue * 100 if total_base_revenue > 0 else 0.0, 1
        ),
        "BaseRevenue": total_base_revenue,
        "PromoEffectiveness": round(promo_effectiveness, 3),
        "Spend": total_spend,
        "Incremental": total_incremental,
        "IncrementalUnits": (
            total_incremental_units
        ),
        "QtyActual": total_qty_actual,
        "QtyBase": total_qty_base,
        "VolumeFactor": float(
            volume_factor
        ),
        "NegativeSkuCount": (
            negative_skus
        ),
        "SkuCount": int(
            len(sku_summary_df)
        ),
        "ReturnPerKc": float(
            portfolio_return
        ),
    }

    return {
        "kpis": kpis,
        "sku_summary": (
            sku_summary_df.to_dict(
                orient="records"
            )
        ),
        "weekly_trends": (
            weekly_trends
        ),
    }



def get_available_historical_years() -> list[str]:
    """Return historical years available for the loaded market."""

    if not promo_engine.is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Promotion engine is still loading.",
        )

    return [
        str(year)
        for year in promo_engine.history_years()
    ]









def get_historical_data(
    year: int,
    classification: str | None = None,
    sku: str | None = None,
    economics: str = "tn",
) -> dict[str, Any]:
    """Return historical data for the selected filters."""

    if not promo_engine.is_ready():
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Promotion engine is still loading."
            ),
        )

    panel_df = (
        promo_engine
        .panel_df
        .copy()
    )

    _validate_required_columns(
        panel_df
    )

    available_years = promo_engine.history_years()

    if year not in available_years:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                f"Year {year} is unavailable. "
                f"Available years: {available_years}"
            ),
        )

    filtered_df = (
        panel_df[
            panel_df[
                "Year"
            ]
            == year
        ]
        .copy()
    )

    filtered_df = (
        filtered_df[
            filtered_df[
                "Classification"
            ].isin(
                _valid_classifications()
            )
        ]
    )

    if classification:
        classification_value = (
            classification
            .strip()
            .upper()
        )

        if (
            classification_value
            not in _valid_classifications()
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_400_BAD_REQUEST
                ),
                detail=(
                    "Invalid classification. Supported values are "
                    + ", ".join(promo_engine.PRICE_BANDS) + "."
                ),
            )

        filtered_df = (
            filtered_df[
                filtered_df[
                    "Classification"
                ]
                == classification_value
            ]
        )

    if sku:
        filtered_df = (
            filtered_df[
                filtered_df[
                    "SKU"
                ].astype(str)
                == str(sku)
            ]
        )

    if filtered_df.empty:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "No historical data was found for "
                "the selected filters."
            ),
        )

    result = (
        _process_historical_data(
            filtered_df,
            economics=economics,
        )
    )

    result["currency"] = promo_engine.currency_info()

    return {
        str(year): result
    }