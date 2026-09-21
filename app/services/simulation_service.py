"""
Simulation service — orchestrates calls to the promo engine and builds the API response.
Ported from promo_api.py _run_common() and helper functions.
"""

import logging

import numpy as np
import pandas as pd
from fastapi import HTTPException

from app.engine import promo_engine
from app.engine.promo_engine import (
    prepare_sku_inputs, build_forecast_sku_inputs, run_portfolio,
    compute_reference_spend, compute_period_spend,
    compute_sku_quarterly_discount_bounds,
)

logger = logging.getLogger(__name__)


def _peak_weeks() -> frozenset:
    """Weeks the timeline treats as peak trading: the market's mandatory
    campaign weeks, from meta.mandatory_campaign_weeks."""
    return frozenset(promo_engine._MANDATORY_CAMPAIGN_WEEKS) | {
        promo_engine.WEEKS_PER_YEAR
    }
def _q_ranges():
    """Quarter windows for the loaded market. Q4 stretches to its last week."""
    return [(q, w0, w1) for q, (w0, w1) in promo_engine.QUARTER_WEEKS.items()]

def _training_end_year() -> int:
    """Last year of observed history for the loaded market."""
    years = promo_engine.history_years()
    return max(years) if years else int(promo_engine.panel_df["Year"].max())


def _get_train_years():
    if "Year" not in promo_engine.panel_df.columns:
        return []
    return sorted(int(y) for y in promo_engine.panel_df["Year"].unique() if int(y) <= _training_end_year())


def _train_yr_str():
    yrs = _get_train_years()
    if len(yrs) >= 2:
        return f"{yrs[0]}–{yrs[-1]}"
    return str(yrs[0]) if yrs else "n/a"


def _quarterly_allocation(opt_results: dict, total_spend: float) -> dict:
    out = {}
    for q, w0, w1 in _q_ranges():
        q_spend = sum(
            float(df.loc[df["week"].between(w0, w1), "promo_spend"].sum())
            for df in opt_results.values()
        )
        out[q] = {"pct": round(q_spend / max(total_spend, 1) * 100, 1), "kc": round(q_spend)}
    return out


def _quarter_proportions_actual(actual_results: dict) -> dict:
    spend = {q: 0.0 for q, _, _ in _q_ranges()}
    for df in actual_results.values():
        for q, w0, w1 in _q_ranges():
            spend[q] += float(df.loc[df["week"].between(w0, w1), "promo_spend"].sum())
    tot = sum(spend.values())
    if tot <= 0:
        return {q: 25.0 for q, _, _ in _q_ranges()}
    return {q: spend[q] / tot * 100.0 for q, _, _ in _q_ranges()}


def _quarter_budgets_from_pcts(total_budget: float, pcts: dict) -> dict:
    tot = sum(float(pcts.get(q, 0)) for q, _, _ in _q_ranges()) or 100.0
    return {q: total_budget * float(pcts.get(q, 0)) / tot for q, _, _ in _q_ranges()}


def _alpha_from_request(alpha, objective: str) -> float:
    if alpha is not None:
        return float(np.clip(alpha, 0.0, 1.0))
    return 0.0 if str(objective).lower() == "turnover" else 1.0


def _sku_band_map(skus) -> dict:
    df = (promo_engine.panel_df[promo_engine.panel_df["SKU"].isin(list(skus))][["SKU", "Classification"]]
          .drop_duplicates())
    return {r["SKU"]: r["Classification"] for _, r in df.iterrows()}


def _sku_volume_uplift_pct(cell_scores, sku, depth: float = 0.10, tol: float = 0.03):
    if cell_scores is None or cell_scores.empty:
        return None
    c = cell_scores[cell_scores["sku"] == sku]
    if c.empty:
        return None
    near = c[(c["discount"] - depth).abs() <= tol]
    if near.empty:
        order = (c["discount"] - depth).abs().argsort()
        near = c.iloc[order[:3]]
    upl = (near["qty_gain"] / near["qty_base"].clip(lower=1e-9)).mean() * 100.0
    return float(upl)


def _agg_by_week(results: dict, col: str) -> np.ndarray:
    arr = np.zeros(53)
    for df in results.values():
        g = df.groupby("week")[col].sum()
        for w, v in g.items():
            wi = int(w)
            if 1 <= wi <= promo_engine.WEEKS_PER_YEAR:
                arr[wi] += float(v)
    return arr


def _best_contiguous_run(values: np.ndarray, mask: np.ndarray):
    best = None
    i = 1
    while i <= promo_engine.WEEKS_PER_YEAR:
        if mask[i]:
            j, s = i, 0.0
            while j <= promo_engine.WEEKS_PER_YEAR and mask[j]:
                s += values[j]
                j += 1
            if best is None or s > best[2]:
                best = (i, j - 1, s)
            i = j
        else:
            i += 1
    return best


def _get_period_bounds(year: int, period: str):
    if period == "Full year":
        return (year, 1), (year, promo_engine.WEEKS_PER_YEAR)
    s, e = promo_engine.QUARTER_WEEKS[period]
    return (year, s), (year, e)


def _actual_from_data(
    sku_inputs: dict,
    economics: str = "tn",
) -> dict:
    """Build historical actuals using the same economics as optimization."""

    actual = {}

    for sku, (df_sku, X, W, t3n_base, qty_base, unit_cost) in sku_inputs.items():
        if "log_price" not in df_sku.columns and "Price" not in df_sku.columns:
            continue

        p_act = (
            df_sku["Price"].values
            if "Price" in df_sku.columns
            else np.exp(df_sku["log_price"].values)
        )

        q_act = (
            df_sku["Qty"].values
            if "Qty" in df_sku.columns
            else np.exp(df_sku["log_qty"].values)
            if "log_qty" in df_sku.columns
            else qty_base
        )

        # Discount remains at sell-out/shelf-price level because this is the
        # price level used by the causal model.
        discount = np.maximum(
            1.0 - p_act / np.maximum(t3n_base, 1e-3),
            0.0,
        )

        if economics == "tn":
            financial_base = t3n_base * promo_engine.K_BRIDGE
            financial_actual = p_act * promo_engine.K_BRIDGE
        else:
            financial_base = t3n_base
            financial_actual = p_act

        actual[sku] = pd.DataFrame({
            "week": df_sku["Week"].values,
            "discount": discount,
            "qty_promo": q_act,
            "rev_promo": (financial_actual * q_act).round(2),
            "profit_promo": (
                (financial_actual - unit_cost) * q_act
            ).round(2),
            "promo_spend": (
                q_act * np.maximum(
                    financial_base - financial_actual,
                    0.0,
                )
            ).round(2),
        })

    return actual


def _timeline_codes(act_disc, opt_disc, week_nums) -> list:
    codes = [0] * promo_engine.WEEKS_PER_YEAR
    for a, o, w in zip(act_disc, opt_disc, week_nums):
        idx = int(w) - 1
        if idx < 0 or idx >= promo_engine.WEEKS_PER_YEAR:
            continue
        if a < 0.005 and o < 0.005:
            codes[idx] = 0
        elif a < 0.005 and o >= 0.005:
            codes[idx] = 1
        elif a >= 0.005 and o >= a + 0.01:
            codes[idx] = 2
        elif a >= 0.005 and 0.005 <= o <= a - 0.01:
            codes[idx] = 3
        elif a >= 0.005 and o < 0.005:
            codes[idx] = 0 if (idx + 1) in _peak_weeks() else 4
        else:
            codes[idx] = 0
    return codes


def _promo_weeks(results: dict) -> int:
    return sum(int((df["discount"] > 0.005).sum()) for df in results.values())


def _totals(results: dict):
    rev = sum(df["rev_promo"].sum() for df in results.values())
    profit = sum(df["profit_promo"].sum() for df in results.values())
    spend = sum(df["promo_spend"].sum() for df in results.values())
    qty = sum(df["qty_promo"].sum() for df in results.values()
              if "qty_promo" in df.columns)
    return rev, profit, spend, qty


def _compute_igm(sku_inputs: dict, results: dict, economics: str = "tn") -> float:
    """IGM = (TN_price − COGS) × qty — COGS only, no TPW/OFSE.
    Stakeholder definition (2026-09-16): IGM = ASP − VAT − PPWF (excl. STTI) − COGS.
    The existing 'profit' field deducts CONTRIB_COST_RATE (TPW+OFSE) on top;
    IGM intentionally omits that layer so the two metrics stay distinct."""
    total = 0.0
    for sku, df in results.items():
        if sku not in sku_inputs:
            continue
        _, _, _, t3n_base, _, unit_cost = sku_inputs[sku]
        t3n_arr = np.asarray(t3n_base, dtype=float)
        if economics == "tn":
            mean_tn = t3n_arr.mean() * promo_engine.K_BRIDGE
            cogs = unit_cost - promo_engine.CONTRIB_COST_RATE * mean_tn
        else:
            cogs = unit_cost - promo_engine.LEGACY_TRADE_COST_RATE * t3n_arr.mean()
        # rev_promo = net_price_promo × qty_promo by construction, so
        # IGM = (net_price - COGS) × qty = rev_promo - COGS × qty.
        # Using rev_promo avoids the KeyError on _actual_from_data results
        # which omit net_price_promo from their minimal DataFrame.
        igm_col = df["rev_promo"] - cogs * df["qty_promo"]
        total += float(igm_col.sum())
    return total


def _weekly_units_agg(results: dict, col: str = "qty_promo") -> dict:
    """Sum a unit column per week across all SKUs."""
    frames = [df[["week", col]] for df in results.values() if col in df.columns]
    if not frames:
        return {}
    return pd.concat(frames, ignore_index=True).groupby("week")[col].sum().to_dict()


def _weekly_units_per_sku(results: dict, col: str = "qty_promo") -> dict:
    """Per-SKU weekly unit arrays, keyed by SKU then week."""
    out: dict = {}
    for sku, df in results.items():
        if col in df.columns:
            out[str(sku)] = df.groupby("week")[col].sum().to_dict()
    return out


def _build_weekly_chart_units(
    base_results: dict,
    actual_results: dict,
    opt_results: dict,
    all_weeks: list,
    compare_vs_base: bool,
) -> dict:
    """Weekly unit chart data — base, actual, optimal — at portfolio and per-SKU level."""
    base_wk   = _weekly_units_agg(base_results,   "qty_base")
    opt_wk    = _weekly_units_agg(opt_results,     "qty_promo")
    act_wk    = _weekly_units_agg(actual_results,  "qty_promo")

    base_sku  = _weekly_units_per_sku(base_results,  "qty_base")
    opt_sku   = _weekly_units_per_sku(opt_results,   "qty_promo")
    act_sku   = _weekly_units_per_sku(actual_results, "qty_promo")

    def _arr(d: dict) -> list:
        return [round(float(d.get(w, 0))) for w in all_weeks]

    # Revenue and spend per SKU per week — needed for per-cell effectiveness
    # on the Promo Effectiveness heat map tab.
    def _rev_per_sku(results: dict, col: str) -> dict:
        out: dict = {}
        for sku, df in results.items():
            if col in df.columns:
                out[str(sku)] = df.groupby("week")[col].sum().to_dict()
        return out

    opt_rev_sku   = _rev_per_sku(opt_results,  "rev_promo")
    base_rev_sku  = _rev_per_sku(base_results, "rev_promo")
    opt_spend_sku = _rev_per_sku(opt_results,  "promo_spend")

    def _farr(d: dict) -> list:
        return [round(float(d.get(w, 0)), 2) for w in all_weeks]

    skus = sorted(set(base_sku) | set(opt_sku))
    per_sku = {
        sku: {
            "base":      _arr(base_sku.get(sku, {})),
            "optimal":   _arr(opt_sku.get(sku, {})),
            "actual":    _arr(act_sku.get(sku, {})) if not compare_vs_base else _arr(base_sku.get(sku, {})),
            "opt_rev":   _farr(opt_rev_sku.get(sku, {})),
            "base_rev":  _farr(base_rev_sku.get(sku, {})),
            "opt_spend": _farr(opt_spend_sku.get(sku, {})),
        }
        for sku in skus
    }

    return {
        "weeks":   all_weeks,
        "base":    _arr(base_wk),
        "optimal": _arr(opt_wk),
        "actual":  _arr(act_wk) if not compare_vs_base else _arr(base_wk),
        "per_sku": per_sku,
    }


def _weekly_agg(results: dict, objective: str = "profit") -> dict:
    col = "rev_promo" if objective == "turnover" else "profit_promo"
    frames = [df[["week", col]] for df in results.values()]
    if not frames:
        return {}
    combined = pd.concat(frames, ignore_index=True)
    return combined.groupby("week")[col].sum().to_dict()


def _fmt_kc(v: float, sign: bool = False) -> str:
    prefix = "+" if (sign and v >= 0) else ""
    return f"{prefix}{v:,.0f}"


def _build_tiers_from_portfolio(opt_results, actual_results, base_results, objective="profit"):
    rows = []
    for sku in opt_results:
        df_opt = opt_results[sku].drop_duplicates(subset=["week"]).set_index("week")
        df_act = actual_results.get(sku, base_results[sku]).drop_duplicates(subset=["week"]).set_index("week")
        all_weeks = sorted(set(df_opt.index) | set(df_act.index))
        for week in all_weeks:
            opt_disc = float(df_opt.at[week, "discount"]) if week in df_opt.index else 0.0
            act_disc = float(df_act.at[week, "discount"]) if week in df_act.index else 0.0
            metric_col = "rev_promo" if objective == "turnover" else "profit_promo"
            opt_metric = float(df_opt.at[week, metric_col]) if week in df_opt.index else 0.0
            act_metric = float(df_act.at[week, metric_col]) if week in df_act.index else 0.0

            if abs(opt_disc - act_disc) < 0.005:
                continue

            gain = opt_metric - act_metric

            if opt_disc > 0 and act_disc < 0.005:
                if gain < 0:
                    continue
                action_type = "add"
                action_txt = f"Add {opt_disc*100:.0f}% discount — new promotional activity"
            elif opt_disc > act_disc + 0.005:
                if gain < 0:
                    continue
                action_type = "deepen"
                action_txt = f"Deepen from {act_disc*100:.0f}% to {opt_disc*100:.0f}% discount"
            elif opt_disc > 0 and opt_disc < act_disc - 0.005:
                action_type = "soften"
                action_txt = f"Soften from {act_disc*100:.0f}% to {opt_disc*100:.0f}% discount"
            elif opt_disc < 0.005 and act_disc > 0.005:
                if week in _peak_weeks():
                    continue
                action_type = "hold"
                action_txt = f"Hold at list price — remove {act_disc*100:.0f}% discount"
            else:
                continue

            rows.append({
                "sku": sku, "week": week, "opt_disc": opt_disc, "act_disc": act_disc,
                "gain": round(gain), "action_type": action_type, "action_txt": action_txt,
            })

    if not rows:
        empty = {"count": 0, "total_gain": 0, "actions": []}
        return {"definitely_do": empty, "worth_considering": empty, "minor_impact": empty}

    abs_gains = sorted(abs(r["gain"]) for r in rows)
    n = len(abs_gains)
    p33 = abs_gains[max(0, n // 3 - 1)]
    p67 = abs_gains[max(0, 2 * n // 3 - 1)]

    buckets = {"Definitely do": [], "Worth considering": [], "Minor impact": []}
    for r in rows:
        g = abs(r["gain"])
        if g >= p67:
            buckets["Definitely do"].append(r)
        elif g >= p33:
            buckets["Worth considering"].append(r)
        else:
            buckets["Minor impact"].append(r)

    def _pack(tier_rows):
        sorted_rows = sorted(tier_rows, key=lambda r: abs(r["gain"]), reverse=True)
        total = sum(r["gain"] for r in sorted_rows)
        return {
            "count": len(sorted_rows),
            "total_gain": round(total),
            "actions": [{
                "sku": r["sku"], "week": r["week"],
                "weeks_label": f"Week {r['week']}",
                "discount_text": (f"{r['opt_disc']*100:.0f}% discount" if r["opt_disc"] > 0 else "list price"),
                "action_text": r["action_txt"],
                "impact": r["gain"],
                "action_type": r["action_type"],
            } for r in sorted_rows],
        }

    return {
        "definitely_do": _pack(buckets["Definitely do"]),
        "worth_considering": _pack(buckets["Worth considering"]),
        "minor_impact": _pack(buckets["Minor impact"]),
    }


def _build_why_reasons(cell_scores, actual_results, opt_results, base_results,
                       sku_inputs=None, objective: str = "profit",
                       compare_vs_base: bool = False) -> list:
    """Dynamic insight engine (Decision 8). Computes candidate insights across
    categories A (timing), B (depth), D (SKU winners), E (budget ROI) plus a light
    elasticity-based evidence note, scores each by Kč impact, and surfaces the top
    few. `compare_vs_base` True == plan mode (forward vs no-promo); False == retro
    (past tense vs actuals)."""
    if cell_scores is None or cell_scores.empty or not sku_inputs:
        return []

    is_plan      = compare_vs_base
    metric_col   = "rev_promo" if objective == "turnover" else "profit_promo"
    word         = "revenue"   if objective == "turnover" else "profit"
    skus         = list(sku_inputs.keys())

    def _msum(results, sku, col):
        df = results.get(sku) if sku in results else None
        return float(df[col].sum()) if df is not None else 0.0

    sku_opt       = {s: _msum(opt_results,    s, metric_col)     for s in skus}
    sku_act       = {s: float(actual_results.get(s, base_results[s])[metric_col].sum())   for s in skus}
    sku_opt_spend = {s: _msum(opt_results,    s, "promo_spend")  for s in skus}
    sku_act_spend = {s: float(actual_results.get(s, base_results[s])["promo_spend"].sum()) for s in skus}

    def _avg_depth(results, s):
        if s not in results:
            return 0.0
        d = results[s]["discount"].values
        d = d[d > 0.005]
        return float(d.mean()) if len(d) else 0.0

    # Week-indexed portfolio aggregates
    opt_gain_wk  = _agg_by_week(opt_results, metric_col) - _agg_by_week(base_results, metric_col)
    opt_spend_wk = _agg_by_week(opt_results, "promo_spend")
    act_spend_wk = _agg_by_week(actual_results, "promo_spend")

    cands = []  # each: {score, cat, num, title, body}

    # ── Category A — Timing ───────────────────────────────────────────────
    miss_mask = (opt_spend_wk > 1) & (act_spend_wk <= 1) if not is_plan else (opt_spend_wk > 1)
    run = _best_contiguous_run(opt_gain_wk, miss_mask)
    if run and run[2] > 0:
        s, e, g = run
        wk_lbl = f"Wk {s}" if s == e else f"Wk {s}–{e}"
        if is_plan:
            title = f"Weeks {s}–{e} are your highest-elasticity window"
            body  = (f"The causal model shows strongest price response in weeks {s}–{e} — "
                     f"<strong>{g:,.{promo_engine.PRICE_DECIMALS}f} {promo_engine.CURRENCY_SYMBOL} incremental {word}</strong> available here. "
                     f"Concentrate promo activity in this window.")
        else:
            title = f"Weeks {s}–{e} have high elasticity but were not promoted"
            body  = (f"The model estimates <strong>{g:,.{promo_engine.PRICE_DECIMALS}f} {promo_engine.CURRENCY_SYMBOL} of {word} upside</strong> in weeks "
                     f"{s}–{e} — but no historical promo ran there. This is the biggest timing gap.")
        cands.append({"score": g, "cat": "TIMING", "num": wk_lbl, "title": title, "body": body})

    if not is_plan:
        over_mask = (act_spend_wk > 1) & (opt_spend_wk <= 1)
        run = _best_contiguous_run(act_spend_wk, over_mask)
        if run and run[2] > 0:
            s, e, sp = run
            cands.append({
                "score": sp, "cat": "TIMING",
                "num":   f"−{sp:,.{promo_engine.PRICE_DECIMALS}f} {promo_engine.CURRENCY_SYMBOL}",
                "title": f"Weeks {s}–{e} show low elasticity — promos there are inefficient",
                "body":  (f"Promos in weeks {s}–{e} cost <strong>{sp:,.{promo_engine.PRICE_DECIMALS}f} {promo_engine.CURRENCY_SYMBOL}</strong> but the causal "
                          f"model finds minimal price response — demand there doesn't need a discount."),
            })

    # ── Category D — SKU concentration ─────────────────────────────────────
    gaps      = {s: sku_opt[s] - sku_act[s] for s in skus}
    total_gap = sum(v for v in gaps.values() if v > 0) or 1.0
    # Top N SKUs by opportunity
    sorted_gaps = sorted(((s, g) for s, g in gaps.items() if g > 0), key=lambda x: x[1], reverse=True)
    if sorted_gaps:
        top_n = min(3, len(sorted_gaps))
        top_skus = sorted_gaps[:top_n]
        top_pct = sum(g for _, g in top_skus) / total_gap * 100
        top_names = ", ".join(s for s, _ in top_skus)
        top_value = sum(g for _, g in top_skus)
        cands.append({
            "score": top_value, "cat": "CONCENTRATION",
            "num":   f"Top {top_n} = {top_pct:.0f}%",
            "title": f"Top {top_n} SKUs account for {top_pct:.0f}% of portfolio opportunity",
            "body":  (f"<strong>{top_names}</strong> together drive <strong>{top_pct:.0f}%</strong> of the "
                      f"total {word} uplift (+{top_value:,.{promo_engine.PRICE_DECIMALS}f} {promo_engine.CURRENCY_SYMBOL}). "
                      f"Concentrate promo investment on these for highest impact."),
        })

    if not is_plan:
        destroyers = [(s, sku_act_spend[s] - sku_opt_spend[s]) for s in skus
                      if sku_act_spend[s] > 1 and sku_opt_spend[s] < 0.2 * sku_act_spend[s]
                      and sku_opt[s] >= sku_act[s] - 1]
        if destroyers:
            n_dest = len(destroyers)
            total_saved = sum(sv for _, sv in destroyers)
            dest_names = ", ".join(s for s, _ in sorted(destroyers, key=lambda x: x[1], reverse=True)[:3])
            cands.append({
                "score": total_saved, "cat": "CONCENTRATION",
                "num":   f"{n_dest} SKUs",
                "title": f"{n_dest} SKUs show no measurable response — {total_saved:,.{promo_engine.PRICE_DECIMALS}f} {promo_engine.CURRENCY_SYMBOL} reallocatable",
                "body":  (f"<strong>{dest_names}</strong>{' and others' if n_dest > 3 else ''} "
                          f"spent <strong>{total_saved:,.{promo_engine.PRICE_DECIMALS}f} {promo_engine.CURRENCY_SYMBOL}</strong> on promotions but the causal model "
                          f"finds no incremental volume. This budget can be redeployed to responsive SKUs."),
            })

    # ── Category B — Depth ────────────────────────────────────────────────
    if not is_plan:
        depth_data = []
        for s in skus:
            od, ad = _avg_depth(opt_results, s), _avg_depth(actual_results, s)
            if ad > 0.005 and od > 0.005:
                depth_data.append((s, od, ad))
        if depth_data:
            over_discounted = [(s, od, ad) for s, od, ad in depth_data if od < ad - 0.02]
            under_discounted = [(s, od, ad) for s, od, ad in depth_data if od > ad + 0.02]
            avg_act = float(np.mean([ad for _, _, ad in depth_data])) * 100
            avg_opt = float(np.mean([od for _, od, _ in depth_data])) * 100
            total_depth_savings = sum(max(0.0, sku_act_spend[s] - sku_opt_spend[s])
                                      for s, _, _ in over_discounted)
            if over_discounted and len(over_discounted) >= len(depth_data) * 0.3:
                cands.append({
                    "score": max(total_depth_savings, 1.0), "cat": "DEPTH",
                    "num":   f"{avg_act:.0f}% → {avg_opt:.0f}%",
                    "title": (f"{len(over_discounted)} of {len(depth_data)} SKUs are discounted "
                              f"deeper than their elasticity supports"),
                    "body":  (f"Portfolio average depth is <strong>{avg_act:.0f}%</strong> but the causal "
                              f"response curve peaks at <strong>{avg_opt:.0f}%</strong> on average. "
                              f"Reducing depth on over-discounted SKUs saves "
                              f"<strong>{total_depth_savings:,.{promo_engine.PRICE_DECIMALS}f} {promo_engine.CURRENCY_SYMBOL}</strong> without losing volume."),
                })
            elif under_discounted:
                cands.append({
                    "score": 1.0, "cat": "DEPTH",
                    "num":   f"{avg_act:.0f}% → {avg_opt:.0f}%",
                    "title": f"Portfolio elasticity supports slightly deeper discounting",
                    "body":  (f"Average actual depth is <strong>{avg_act:.0f}%</strong> but the model "
                              f"finds continued volume response up to <strong>{avg_opt:.0f}%</strong> "
                              f"for {len(under_discounted)} SKUs — volume opportunity at current depth."),
                })
    else:
        pos = cell_scores[cell_scores["profit_gain"] > 0]
        if not pos.empty:
            avg_opt_depth = float(pos.sort_values("profit_gain", ascending=False)
                                  .drop_duplicates(subset=["sku", "week"])["discount"].mean()) * 100
            cands.append({
                "score": 1.0, "cat": "DEPTH",
                "num":   f"{avg_opt_depth:.0f}%",
                "title": f"Optimal depth averages {avg_opt_depth:.0f}% across the portfolio",
                "body":  (f"The causal response curve is concave — beyond <strong>{avg_opt_depth:.0f}%</strong> "
                          f"discount, additional depth adds cost without meaningful volume gain."),
            })

    # ── Category E — Budget efficiency (per-quarter ROI) ──────────────────
    q_roi = {}
    for q, w0, w1 in _q_ranges():
        opt_inc = sum(float(df.loc[df["week"].between(w0, w1), metric_col].sum()
                            - base_results[s].loc[base_results[s]["week"].between(w0, w1), metric_col].sum())
                      for s, df in opt_results.items())
        opt_sp  = float(opt_spend_wk[w0:w1+1].sum())
        if opt_sp > 1:
            q_roi[q] = opt_inc / opt_sp
    if len(q_roi) >= 2:
        best_q = max(q_roi, key=q_roi.get)
        worst_q = min(q_roi, key=q_roi.get)
        if q_roi[best_q] - q_roi[worst_q] > 0.3:
            worst_sp = float(sum(opt_spend_wk[w0:w1+1].sum()
                                 for q, w0, w1 in _q_ranges() if q == worst_q))
            cands.append({
                "score": (q_roi[best_q] - q_roi[worst_q]) * worst_sp, "cat": "EFFICIENCY",
                "num":   f"{worst_q}",
                "title": f"{worst_q} has the lowest return per {promo_engine.CURRENCY_SYMBOL} of promo spend",
                "body":  (f"{worst_q} returns <strong>{q_roi[worst_q]*100:.0f}%</strong> per {promo_engine.CURRENCY_SYMBOL} vs. "
                          f"{best_q}'s <strong>{q_roi[best_q]*100:.0f}%</strong>. "
                          f"Elasticity is structurally lower in {worst_q} — budget works harder in {best_q}."),
            })

    # Pick the top insight from each distinct category (max 1 per category),
    # ranked by Kč impact, up to 3 insights.
    cands.sort(key=lambda c: c["score"], reverse=True)
    out, seen_cats = [], set()
    for c in cands:
        cat = c.get("cat", "OTHER")
        if cat in seen_cats:
            continue
        seen_cats.add(cat)
        out.append({"num": c["num"], "tag": cat,
                    "title": c["title"], "body": c["body"]})
        if len(out) >= 3:
            break
    return out

def _classify_rec(profit_uplift, act_profit, avg_act_depth, avg_opt_depth, act_weeks, opt_weeks):
    pct = profit_uplift / max(abs(act_profit), 1) * 100
    if pct < 0:
        return "Model boundary"
    if pct < 0.5:
        return "Near-optimal"
    if avg_opt_depth < avg_act_depth - 0.02 and abs(opt_weeks - act_weeks) < 5:
        return "Depth reduction"
    if opt_weeks < act_weeks * 0.88:
        return "Seasonal reshape"
    if opt_weeks > act_weeks * 1.12:
        return "Under-utilising"
    return "Seasonal reshape"


def _classify_rec_turnover(rev_uplift, act_rev, opt_spend, act_spend):
    pct = rev_uplift / max(abs(act_rev), 1) * 100
    if pct < 0:
        return "Turnover deficit"
    if pct < 0.5:
        return "Near-optimal"
    spend_delta = (opt_spend - act_spend) / max(act_spend, 1)
    if spend_delta > 0.10:
        return "Invest to grow"
    if spend_delta < -0.10:
        return "Efficiency win"
    return "Seasonal reshape"


def _build_verdict(rec_type, profit_uplift, act_profit, avg_act_depth, avg_opt_depth,
                   act_weeks, opt_weeks, objective="profit",
                   rev_uplift=0, act_rev=1, opt_spend=0, act_spend=1):
    if objective == "turnover":
        rev_pct = rev_uplift / max(abs(act_rev), 1) * 100
        if rec_type == "Turnover deficit":
            return (f"Despite unconstrained budget, the model "
                    f"<strong>cannot improve on historical revenue</strong> "
                    f"({abs(rev_pct):.1f}% shortfall vs actual). "
                    f"This SKU mix has very low or negative measured elasticity — "
                    f"discounts are not generating enough volume to offset the price reduction. "
                    f"<strong>Review list pricing or promotional mechanics.</strong>")
        if rec_type == "Near-optimal":
            return (f"Revenue is close to its maximum given measured elasticity. "
                    f"Only <strong>{rev_pct:.1f}%</strong> of additional turnover available. "
                    f"<strong>The current allocation already captures most volume uplift.</strong>")
        spend_delta_pct = (opt_spend - act_spend) / max(act_spend, 1) * 100
        if spend_delta_pct > 10:
            spend_mult = opt_spend / max(act_spend, 1)
            return (f"The model identifies <strong>high-elasticity windows worth investing in</strong>. "
                    f"Increasing promo spend by <strong>{spend_mult:.1f}×</strong> unlocks "
                    f"<strong>{rev_pct:.0f}% more revenue</strong>. "
                    f"The commercial case is volume growth: more targeted investment, more turnover.")
        if spend_delta_pct < -10:
            spend_save_pct = abs(spend_delta_pct)
            return (f"<strong>Smarter allocation delivers more revenue for less spend</strong>. "
                    f"Redirecting budget into higher-elasticity windows drives "
                    f"<strong>{rev_pct:.0f}% more turnover</strong> "
                    f"while cutting promo spend by <strong>{spend_save_pct:.0f}%</strong>.")
        return (f"Rebalancing the promotional calendar into "
                f"<strong>higher-elasticity windows</strong> delivers "
                f"<strong>{rev_pct:.0f}% more revenue</strong> "
                f"at similar spend levels. Same investment, better timing.")

    pct = profit_uplift / max(abs(act_profit), 1) * 100
    if rec_type == "Model boundary":
        return (f"The model finds that <strong>historical spend can be cut significantly</strong> "
                f"while keeping profit within {abs(pct):.1f}% of what was actually achieved. "
                f"This indicates <strong>low measured elasticity</strong> for this SKU mix — "
                f"discounts are generating less incremental volume than the budget they consume. "
                f"<strong>The commercial case is efficiency, not uplift</strong>: same outcomes, lower investment.")
    if rec_type == "Near-optimal":
        return (f"The current plan is <strong>already close to optimal</strong>. "
                f"Only <strong>{pct:.1f}%</strong> of profit left on the table. "
                f"<strong>No major reallocation recommended.</strong>")
    if rec_type == "Depth reduction":
        return (f"Keep the same promotional calendar, but "
                f"<strong>soften discount depth from "
                f"{avg_act_depth*100:.0f}% to {avg_opt_depth*100:.0f}%</strong>. "
                f"Current depths outrun measured elasticity — "
                f"estimated <strong>{pct:.1f}% profit improvement</strong>.")
    if rec_type == "Under-utilising":
        return (f"Portfolio is <strong>under-promoted in certain windows</strong>. "
                f"Adding <strong>{opt_weeks - act_weeks} promotion weeks</strong> in "
                f"high-elasticity slots unlocks <strong>{pct:.1f}% more profit</strong>.")
    freed = act_weeks - opt_weeks
    spend_delta_pct = (opt_spend - act_spend) / max(act_spend, 1) * 100
    if spend_delta_pct < -10:
        spend_clause = f"saving <strong>{abs(spend_delta_pct):.0f}% of promo spend</strong>"
    elif spend_delta_pct > 10:
        spend_clause = f"on a <strong>{spend_delta_pct:.0f}% higher budget</strong>"
    else:
        spend_clause = "at broadly flat spend"
    return (f"Shift promo budget into <strong>higher-elasticity windows</strong> and "
            f"<strong>hold list price in low-ROI periods</strong>. "
            f"Earn <strong>{pct:.1f}% more profit</strong> "
            f"in fewer, better-timed windows ({freed:+d} promo weeks) — {spend_clause}.")


def _build_sku_table(sku_inputs, base_results, actual_results, opt_results, cell_scores, objective="profit"):
    pos_gains = (cell_scores.loc[cell_scores["profit_gain"] > 0, "profit_gain"]
                 if not cell_scores.empty else pd.Series(dtype=float))
    p25 = float(pos_gains.quantile(0.25)) if not pos_gains.empty else 0.0
    p75 = float(pos_gains.quantile(0.75)) if not pos_gains.empty else 0.0
    sku_med = (cell_scores[cell_scores["profit_gain"] > 0]
               .groupby("sku")["profit_gain"].median()
               if not cell_scores.empty else pd.Series(dtype=float))
    metric_col = "rev_promo" if objective == "turnover" else "profit_promo"
    rows = []
    for sku in sku_inputs:
        base_p = float(base_results[sku][metric_col].sum())
        actual_p = float(actual_results.get(sku, base_results[sku])[metric_col].sum())
        opt_p = float(opt_results[sku][metric_col].sum())
        opt_spend_sku = float(opt_results[sku]["promo_spend"].sum())
        act_spend_sku = float(actual_results.get(sku, base_results[sku])["promo_spend"].sum())
        med = float(sku_med.get(sku, 0.0))
        conf = ("Definitely do" if med >= p75
                else "Worth considering" if med >= p25
                else "Minor impact")
        opt_roi = round((opt_p - base_p) / opt_spend_sku, 2) if opt_spend_sku > 1 else None
        act_roi = round((actual_p - base_p) / act_spend_sku, 2) if act_spend_sku > 1 else None
        rows.append({"sku": sku, "base_profit": round(base_p), "act_profit": round(actual_p),
                     "opt_profit": round(opt_p), "gain": round(opt_p - actual_p),
                     "act_promo_spend": round(act_spend_sku),
                     "promo_spend": round(opt_spend_sku), "confidence": conf,
                     "roi": opt_roi, "act_roi": act_roi})
    return rows


def _build_elasticity(cell_scores, sku_inputs, alpha: float = 1.0) -> dict:
    """Decision 9 — elasticity section data. Left chart: price elasticity |β| by week
    (when to promote). Right chart: profit/blended-value vs discount depth using the
    same α blend that was used in the optimisation (how deep to go, consistent with
    what the calendar shows)."""
    if cell_scores is None or cell_scores.empty or not sku_inputs:
        return {"series": {}, "weeks": [], "depths": [], "ref_depth": 10, "summary": [],
                "pooled": {"depth_profit": [], "depth_revenue": [], "beta_weekly": []},
                "per_sku": {}, "sku_list": [str(x) for x in (sku_inputs or {}).keys()]}
    skus  = list(sku_inputs.keys())
    bands = _sku_band_map(skus)
    cs = cell_scores.copy()
    # Drop retro-only off-grid `is_actual` candidates so the reference depths are clean.
    if "is_actual" in cs.columns:
        cs = cs[~cs["is_actual"]]
    cs["_band"] = cs["sku"].map(bands)
    cs["_upl"]  = cs["qty_gain"] / cs["qty_base"].clip(lower=1e-9) * 100.0

    weeks = sorted(int(w) for w in cs["week"].unique())

    cs["_base_rev"] = cs["price_base"] * cs["qty_base"]
    # Use the same blended value the optimizer used — so the depth curve and the
    # calendar are answering the same question. alpha=1 → pure profit, alpha=0 →
    # pure revenue, alpha=0.5 → balanced. Normalised by base revenue for comparability.
    cs["_value"]  = alpha * cs["profit_gain_raw"] + (1.0 - alpha) * cs["rev_gain"]
    cs["_pnorm"]  = cs["_value"] / cs["_base_rev"].clip(lower=1e-9) * 100.0

    # β (absolute price elasticity) per cell = |log(qty_promo/qty_base) / log(1-d)|.
    # Theoretically constant across depths for a given SKU-week (constant-elasticity
    # model); averaging across depths gives a robust per-SKU-week estimate.
    # Clipped to [0, 8] to avoid numerical infs at extreme depth/qty combinations.
    cs["_beta"] = (np.log(cs["qty_promo"] / cs["qty_base"].clip(lower=1e-9)) /
                   np.log(1.0 - cs["discount"].clip(upper=0.999))).abs().clip(0, 8)

    # Per SKU-week: mean beta across discount depths (should be ~constant per model)
    sw = cs.groupby(["sku", "week"])["_beta"].mean().reset_index()
    sw["_band"] = sw["sku"].map(bands)

    # series[band] = [{week, median, min, max}] of |β| across selected SKUs in band.
    # Shows WHEN each band is most price-elastic — higher β = more volume response
    # per 1% price move. Band = range across SKUs; centre = median SKU.
    series = {}
    for band in promo_engine.PRICE_BANDS:
        sub = sw[sw["_band"] == band]
        if sub.empty:
            continue
        stats = (sub.groupby("week")["_beta"]
                 .agg(["median", "min", "max"])
                 .reindex(weeks)
                 .reset_index())
        series[band] = [{"week": int(r["week"]),
                         "median": round(float(r["median"]), 2),
                         "min":    round(float(r["min"]),    2),
                         "max":    round(float(r["max"]),    2)}
                        for _, r in stats.iterrows()
                        if not (r[["median", "min", "max"]].isna().any())]

    # Both depth curves filtered by the chosen α's positive-value cells — consistent
    # with what the optimizer actually considers. Y-axis shows profit and revenue
    # respectively so both are always visible regardless of α.
    cs["_pnorm_profit"] = cs["profit_gain_raw"] / cs["_base_rev"].clip(lower=1e-9) * 100.0
    cs["_pnorm_rev"]    = cs["rev_gain"]         / cs["_base_rev"].clip(lower=1e-9) * 100.0

    def _depth_curve_for(metric_col: str, metric_norm_col: str) -> dict:
        # Each curve filters by its own metric > 0 so the chart is self-consistent:
        # profit curve = cells where promos add profit; revenue curve = cells where
        # promos add revenue. Independent of α — the curves show the model's causal
        # estimates, α only determines which cells the optimizer ultimately picks.
        pos = cs[cs[metric_col] > 0]
        out = {}
        for band in promo_engine.PRICE_BANDS:
            sub = pos[pos["_band"] == band]
            if sub.empty:
                continue
            sku_means = sub.groupby(["sku", "discount"])[metric_norm_col].mean().reset_index()
            if sku_means.empty:
                continue
            stats = (sku_means.groupby("discount")[metric_norm_col]
                     .agg(["median", "min", "max"]).reset_index()
                     .sort_values("discount"))
            out[band] = [{"discount": int(round(float(r["discount"]) * 100)),
                          "median": round(float(r["median"]), 2),
                          "min":    round(float(r["min"]),    2),
                          "max":    round(float(r["max"]),    2)}
                         for _, r in stats.iterrows()]
        return out

    depth_curves_profit  = _depth_curve_for("profit_gain_raw", "_pnorm_profit")
    depth_curves_revenue = _depth_curve_for("rev_gain",        "_pnorm_rev")

    # ── Additive (v4): pooled + per-SKU views ────────────────────────────────
    # These extra keys are ignored by the v3 frontend; v4 uses them to offer an
    # "All selected SKUs (pooled)" vs "single SKU" toggle without the price-band
    # split. Nothing above changes, so v3 behavior is unaffected.
    def _pooled_depth(metric_col: str, metric_norm_col: str) -> list:
        # One curve across ALL selected SKUs. Centre = median SKU at each depth;
        # band = min/max across SKUs (same semantics the by-band view uses).
        pos = cs[cs[metric_col] > 0]
        if pos.empty:
            return []
        sku_means = pos.groupby(["sku", "discount"])[metric_norm_col].mean().reset_index()
        stats = (sku_means.groupby("discount")[metric_norm_col]
                 .agg(["median", "min", "max"]).reset_index().sort_values("discount"))
        return [{"discount": int(round(float(r["discount"]) * 100)),
                 "median": round(float(r["median"]), 2),
                 "min":    round(float(r["min"]),    2),
                 "max":    round(float(r["max"]),    2)}
                for _, r in stats.iterrows()]

    def _per_sku_depth(metric_col: str, metric_norm_col: str) -> dict:
        # Per-SKU curve; band = min/max across that SKU's weeks at each depth.
        pos = cs[cs[metric_col] > 0]
        out = {}
        if pos.empty:
            return out
        for sku, sub in pos.groupby("sku"):
            stats = (sub.groupby("discount")[metric_norm_col]
                     .agg(["median", "min", "max"]).reset_index().sort_values("discount"))
            out[sku] = [{"discount": int(round(float(r["discount"]) * 100)),
                         "median": round(float(r["median"]), 2),
                         "min":    round(float(r["min"]),    2),
                         "max":    round(float(r["max"]),    2)}
                        for _, r in stats.iterrows()]
        return out

    # Pooled weekly |β|: median/min/max across ALL selected SKUs per week.
    pooled_beta = []
    if not sw.empty:
        bstats = (sw.groupby("week")["_beta"].agg(["median", "min", "max"])
                  .reindex(weeks).reset_index())
        pooled_beta = [{"week": int(r["week"]),
                        "median": round(float(r["median"]), 2),
                        "min":    round(float(r["min"]),    2),
                        "max":    round(float(r["max"]),    2)}
                       for _, r in bstats.iterrows()
                       if not (r[["median", "min", "max"]].isna().any())]
    # Per-SKU weekly |β|: single line per SKU.
    per_sku_beta = {}
    for sku, sub in sw.groupby("sku"):
        per_sku_beta[str(sku)] = [{"week": int(r["week"]), "value": round(float(r["_beta"]), 2)}
                                  for _, r in sub.sort_values("week").iterrows()]

    pooled = {
        "depth_profit":  _pooled_depth("profit_gain_raw", "_pnorm_profit"),
        "depth_revenue": _pooled_depth("rev_gain",        "_pnorm_rev"),
        "beta_weekly":   pooled_beta,
    }
    per_sku_depth_profit  = _per_sku_depth("profit_gain_raw", "_pnorm_profit")
    per_sku_depth_revenue = _per_sku_depth("rev_gain",        "_pnorm_rev")
    per_sku = {}
    for sku in set(per_sku_depth_profit) | set(per_sku_depth_revenue) | set(per_sku_beta):
        per_sku[str(sku)] = {
            "depth_profit":  per_sku_depth_profit.get(sku, []),
            "depth_revenue": per_sku_depth_revenue.get(sku, []),
            "beta_weekly":   per_sku_beta.get(str(sku), []),
        }

    obj_label = ("Profit" if alpha >= 0.99
                 else "Revenue" if alpha <= 0.01
                 else f"Blended ({int(round(alpha*100))}% profit / {int(round((1-alpha)*100))}% revenue)")
    return {"series": series,
            "depth_curves_profit":  depth_curves_profit,
            "depth_curves_revenue": depth_curves_revenue,
            "weeks": weeks, "obj_label": obj_label,
            # additive v4 fields
            "pooled": pooled, "per_sku": per_sku,
            "sku_list": [str(x) for x in sku_inputs.keys()]}

def _prelaunch_map(sku_inputs):
    out = {}
    for sku, tup in sku_inputs.items():
        df = tup[0]
        if "is_prelaunch" in df.columns and bool(df["is_prelaunch"].any()):
            pre = sorted(int(w) for w in df.loc[df["is_prelaunch"], "Week"].tolist())
            launch = int(df.loc[~df["is_prelaunch"], "Week"].min())
            out[sku] = {"launch_week": launch, "weeks": pre}
    return out


def _build_roi_summary(base_results, actual_results, opt_results, objective):
    metric_col = "rev_promo" if objective == "turnover" else "profit_promo"

    def _roi(results):
        spend = sum(float(df["promo_spend"].sum()) for df in results.values())
        if spend <= 1:
            return None
        inc = sum(float(results[s][metric_col].sum() - base_results[s][metric_col].sum())
                  for s in results if s in base_results)
        return round(inc / spend, 2)

    per_quarter = {}
    for q, w0, w1 in _q_ranges():
        sp = sum(float(df.loc[df["week"].between(w0, w1), "promo_spend"].sum())
                 for df in opt_results.values())
        if sp <= 1:
            per_quarter[q] = None
            continue
        inc = sum(float(opt_results[s].loc[opt_results[s]["week"].between(w0, w1), metric_col].sum()
                        - base_results[s].loc[base_results[s]["week"].between(w0, w1), metric_col].sum())
                  for s in opt_results if s in base_results)
        per_quarter[q] = round(inc / sp, 2)

    return {"optimal": _roi(opt_results), "actual": _roi(actual_results), "per_quarter": per_quarter}


def _build_hist_compare(hist_results, hist_year):
    h_rev, h_profit, h_spend, h_qty = _totals(hist_results)
    h_weeks = _promo_weeks(hist_results)
    h_margin = h_profit / max(h_rev, 1) * 100
    return {
        "turnover": round(h_rev), "profit": round(h_profit),
        "margin": round(h_margin, 1), "qty": round(h_qty),
        "promo_weeks": h_weeks, "promo_spend": round(h_spend), "year": hist_year,
    }


def _budget_sub(opt_spend, act_spend, compare_vs_base, hist_results, hist_year):
    if compare_vs_base and hist_results and hist_year:
        h_spend = sum(float(df["promo_spend"].sum()) for df in hist_results.values())
        return f"vs. {h_spend:,.{promo_engine.PRICE_DECIMALS}f} {promo_engine.CURRENCY_SYMBOL} ({hist_year} actual)"
    if abs(opt_spend - act_spend) / max(act_spend, 1) < 0.05:
        return "Same as historical · reallocated only"
    return f"vs. {act_spend:,.{promo_engine.PRICE_DECIMALS}f} {promo_engine.CURRENCY_SYMBOL} historical"


def run_common(
    sku_inputs, actual_results, budget_cap, disc_grid, alpha,
    discount_bounds, period_label, compare_vs_base=False,
    hist_results=None, hist_year=None, margin_floor=0.0, quarter_budgets=None,
    economics="tn",
):
    """Run the simulation and return a frontend-ready response.

    Expected HTTP errors are preserved. Unexpected failures are logged with
    their full traceback while returning a safe message to the API client.
    """
    try:
        return _run_common_impl(
            sku_inputs=sku_inputs,
            actual_results=actual_results,
            budget_cap=budget_cap,
            disc_grid=disc_grid,
            alpha=alpha,
            discount_bounds=discount_bounds,
            period_label=period_label,
            compare_vs_base=compare_vs_base,
            hist_results=hist_results,
            hist_year=hist_year,
            margin_floor=margin_floor,
            quarter_budgets=quarter_budgets,
            economics=economics,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "Simulation execution failed for period '%s'.",
            period_label,
        )
        raise HTTPException(
            status_code=500,
            detail="Simulation failed. Please try again.",
        ) from exc


# ── Main orchestrator ────────────────────────────────────────────────
def _run_common_impl(
    sku_inputs, actual_results, budget_cap, disc_grid, alpha,
    discount_bounds, period_label, compare_vs_base=False,
    hist_results=None, hist_year=None, margin_floor=0.0, quarter_budgets=None,
    economics="tn",
):
    if not sku_inputs:
        raise HTTPException(status_code=400, detail="No valid SKUs found in data.")

    objective = "profit" if alpha >= 0.5 else "turnover"

    base_results, opt_results, cell_scores, _ = run_portfolio(
        sku_inputs, disc_grid, budget_cap, promo_engine.est_price_f,
        alpha=alpha, discount_bounds=discount_bounds,
        margin_floor=margin_floor, quarter_budgets=quarter_budgets,
        economics=economics,
    )

    if compare_vs_base:
        actual_results = {sku: base_results[sku] for sku in base_results}
    else:
        for sku in sku_inputs:
            if sku not in actual_results:
                actual_results[sku] = base_results[sku]

    base_rev, base_profit, base_spend, base_qty = _totals(base_results)
    act_rev, act_profit, act_spend, act_qty = _totals(actual_results)
    opt_rev, opt_profit, opt_spend, opt_qty = _totals(opt_results)

    # IGM (COGS-only) — computed unconditionally so both metrics are always
    # available on the rail regardless of the chosen optimization objective.
    base_igm = _compute_igm(sku_inputs, base_results, economics)
    act_igm  = _compute_igm(sku_inputs, actual_results, economics)
    opt_igm  = _compute_igm(sku_inputs, opt_results, economics)

    # No-promo base revenue — needed for portfolio-level Promo Effectiveness
    # (incremental revenue / spend).  base_results was simulated at zero
    # discount so rev_promo == baseline revenue for every SKU.  Using
    # base_results avoids a KeyError on actual_results (from _actual_from_data)
    # which omits rev_base from its minimal DataFrame.
    base_rev_total = sum(float(df["rev_promo"].sum()) for df in base_results.values())
    act_base_rev = base_rev_total
    opt_base_rev = base_rev_total

    profit_uplift = opt_profit - act_profit
    rev_uplift = opt_rev - act_rev
    act_weeks = _promo_weeks(actual_results)
    opt_weeks = _promo_weeks(opt_results)
    act_margin = act_profit / max(act_rev, 1) * 100
    opt_margin = opt_profit / max(opt_rev, 1) * 100
    margin_delta = opt_margin - act_margin

    act_disc_all = np.concatenate([df["discount"].values for df in actual_results.values()])
    opt_disc_all = np.concatenate([df["discount"].values for df in opt_results.values()])
    avg_act_depth = float(act_disc_all[act_disc_all > 0.005].mean()) if (act_disc_all > 0.005).any() else 0.0
    avg_opt_depth = float(opt_disc_all[opt_disc_all > 0.005].mean()) if (opt_disc_all > 0.005).any() else 0.0

    if objective == "turnover":
        rec_type = _classify_rec_turnover(rev_uplift, act_rev, opt_spend, act_spend)
    else:
        rec_type = _classify_rec(profit_uplift, act_profit, avg_act_depth, avg_opt_depth, act_weeks, opt_weeks)
    pct_uplift = profit_uplift / max(abs(act_profit), 1) * 100

    train_yrs = _get_train_years()
    n_pos = int((cell_scores["profit_gain"] > 0).sum()) if not cell_scores.empty else 0
    n_skus_run = len(sku_inputs)
    n_total = int(len(cell_scores)) if not cell_scores.empty else 1
    pos_pct = n_pos / max(n_total, 1)
    data_sub = f"Trained on {len(train_yrs)} years of causal data ({_train_yr_str()}) · {n_skus_run} SKU{'s' if n_skus_run != 1 else ''} selected"
    conf_label = (f"High · {n_pos} of {n_total} cells positive ({pos_pct:.0%})"
                  if pos_pct >= 0.30 else
                  f"Medium · {n_pos} of {n_total} cells positive ({pos_pct:.0%})"
                  if pos_pct >= 0.10 else
                  f"Low · {n_pos} of {n_total} cells positive ({pos_pct:.0%})")

    arrow = "↑" if margin_delta >= 0 else "↓"
    col = "#1F6B47" if margin_delta >= 0 else "#D94F30"
    margin_html = (f"{opt_margin:.1f}% "
                   f"<span style=\"color:{col};font-size:13px;font-family:'DM Sans';\">"
                   f"{arrow}{abs(margin_delta):.1f}pp</span>")

    eff_turnover = opt_rev + (act_spend - opt_spend)
    delta_eff = eff_turnover - act_rev
    delta_eff_pct = delta_eff / max(abs(act_rev), 1) * 100

    vs_label = "vs no-promo baseline" if compare_vs_base else "vs historical actual"

    if objective == "turnover":
        hero_value = _fmt_kc(opt_rev)
        hero_label = "Optimal revenue"
        delta_val = rev_uplift
        delta_pct = rev_uplift / max(abs(act_rev), 1) * 100
    else:
        hero_value = _fmt_kc(opt_profit)
        hero_label = "Optimal profit"
        delta_val = profit_uplift
        delta_pct = pct_uplift

    sign = "+" if delta_val >= 0 else ""
    hero_delta = f"{sign}{_fmt_kc(delta_val)} · {delta_pct:+.1f}% {vs_label}"
    delta_up = delta_val >= 0

    tiers = _build_tiers_from_portfolio(opt_results, actual_results, base_results, objective)

    timeline = {}
    for sku in sku_inputs:
        if sku not in opt_results or sku not in actual_results:
            continue
        merged = (
            opt_results[sku][["week", "discount"]].drop_duplicates("week").rename(columns={"discount": "opt_disc"})
            .merge(
                actual_results[sku][["week", "discount"]].drop_duplicates("week").rename(columns={"discount": "act_disc"}),
                on="week", how="outer",
            ).fillna(0).sort_values("week")
        )
        codes = _timeline_codes(merged["act_disc"].values, merged["opt_disc"].values, merged["week"].values)
        opt_disc_arr = [0] * promo_engine.WEEKS_PER_YEAR
        act_disc_arr = [0] * promo_engine.WEEKS_PER_YEAR
        for _, row in merged.iterrows():
            idx = int(row["week"]) - 1
            if 0 <= idx < promo_engine.WEEKS_PER_YEAR:
                opt_disc_arr[idx] = round(float(row["opt_disc"]) * 100)
                act_disc_arr[idx] = round(float(row["act_disc"]) * 100)
        timeline[sku] = {"codes": codes, "opt_disc": opt_disc_arr, "act_disc": act_disc_arr}

    base_weekly = _weekly_agg(base_results, objective)
    actual_weekly = _weekly_agg(actual_results, objective)
    opt_weekly = _weekly_agg(opt_results, objective)
    all_weeks = sorted(set(base_weekly) | set(actual_weekly) | set(opt_weekly))
    weekly_chart = {
        "weeks": all_weeks,
        "base": [round(base_weekly.get(w, 0)) for w in all_weeks],
        "actual": [round(actual_weekly.get(w, 0)) for w in all_weeks],
        "optimal": [round(opt_weekly.get(w, 0)) for w in all_weeks],
    }

    return {
        "status": "ok",
        "objective": objective,
        "hero": {
            "eyebrow": period_label,
            "pill_text": rec_type,
            "value": hero_value,
            "label": hero_label,
            "delta": hero_delta,
            "verdict": _build_verdict(rec_type, profit_uplift, act_profit,
                                      avg_act_depth, avg_opt_depth, act_weeks, opt_weeks,
                                      objective=objective,
                                      rev_uplift=rev_uplift, act_rev=act_rev,
                                      opt_spend=opt_spend, act_spend=act_spend),
            "confidence": conf_label,
            "data_sub": data_sub,
            "margin_html": margin_html,
            "budget_used": f"{opt_spend:,.{promo_engine.PRICE_DECIMALS}f} {promo_engine.CURRENCY_SYMBOL}",
            "budget_sub": _budget_sub(opt_spend, act_spend, compare_vs_base, hist_results, hist_year),
        },
        "tiers": tiers,
        "why_reasons": _build_why_reasons(cell_scores, actual_results, opt_results, base_results,
                                          sku_inputs=sku_inputs, objective=objective,
                                          compare_vs_base=compare_vs_base),
        "compare": {
            "current": {
                "turnover": round(act_rev), "profit": round(act_profit),
                "margin": round(act_margin, 1), "qty": round(act_qty),
                "promo_weeks": act_weeks, "promo_spend": round(act_spend),
                "igm": round(act_igm),
                "igm_margin_pct": round(act_igm / max(act_rev, 1) * 100, 1),
                "base_revenue": round(act_base_rev),
                "promo_effectiveness": round(
                    (act_rev - act_base_rev) / act_spend, 3
                ) if act_spend > 1 else 0.0,
            },
            **({"historical": _build_hist_compare(hist_results, hist_year)} if hist_results else {}),
            "recommended": {
                "turnover": round(opt_rev), "profit": round(opt_profit),
                "margin": round(opt_margin, 1), "qty": round(opt_qty),
                "promo_weeks": opt_weeks, "promo_spend": round(opt_spend),
                "effective_turnover": round(eff_turnover),
                "delta_effective_turnover": round(delta_eff),
                "delta_effective_pct": round(delta_eff_pct, 1),
                "igm": round(opt_igm),
                "igm_margin_pct": round(opt_igm / max(opt_rev, 1) * 100, 1),
                "igm_delta": round(opt_igm - act_igm),
                "base_revenue": round(opt_base_rev),
                "promo_effectiveness": round(
                    (opt_rev - opt_base_rev) / opt_spend, 3
                ) if opt_spend > 1 else 0.0,
            },
        },
        "compare_vs_base": compare_vs_base,
        "quarterly_allocation": _quarterly_allocation(opt_results, opt_spend),
        "quarterly_actual": _quarterly_allocation(actual_results, act_spend),
        "quarterly_envelopes": ({q: round(float(v)) for q, v in quarter_budgets.items()}
                                if quarter_budgets else None),
        "timeline": timeline,
        "weekly_chart": weekly_chart,
        "deep_dive": {"sku_table": _build_sku_table(
            sku_inputs, base_results, actual_results, opt_results, cell_scores,
            objective=objective)},
        "elasticity": _build_elasticity(cell_scores, sku_inputs, alpha=alpha),
        "roi": _build_roi_summary(base_results, actual_results, opt_results, objective),
        "prelaunch": _prelaunch_map(sku_inputs),
        "volume_factor": round(opt_qty / max(base_qty, 1), 2),
        "volume_factor_actual": round(act_qty / max(base_qty, 1), 2),
        "currency": promo_engine.currency_info(),
        "weekly_chart_units": _build_weekly_chart_units(
            base_results, actual_results, opt_results,
            all_weeks, compare_vs_base,
        ),
    }