"""
Generate the combined DE Diamond Clean stock-depletion + HVSE Q4 2026 Amazon-menu
analysis, at the SHIPPED 40% discount ceiling (grid NOT extended).

Two runs, merged:
  A) Stock-priority SKUs  — unconstrained, NO margin floor (clearance beats margin)
  B) Amazon-menu SKUs     — unconstrained, 15% margin floor (no clearance
                            justification for selling below cost)

Verified safe to split: in unconstrained mode there is no cross-SKU budget
competition, so per-SKU results are bit-identical to a single combined run.
"""
import json
import pickle
import warnings

warnings.filterwarnings("ignore")

from app.engine import promo_engine
from app.engine.promo_engine import (
    build_forecast_sku_inputs,
    compute_sku_quarterly_discount_bounds,
    run_portfolio,
)
from app.routers.simulation_router import run_plan
from app.schemas.requests import PlanRequest

MARGIN_FLOOR_MENU = 15.0

with open("DE_Amazon_RTB.pkl", "rb") as f:
    data = pickle.load(f)
promo_engine.init_engine(data)

# Discount grid left untouched. Extending it makes the optimizer pin to whatever
# ceiling is set (identical week pattern at 50% and 60%); the shipped 40% grid
# reproduces the trusted 2026-09-10 report exactly.
print("Discount grid (unmodified): {:.2f} - {:.2f} ({} levels)".format(
    promo_engine.DISCOUNT_GRID_ALL.min(), promo_engine.DISCOUNT_GRID_ALL.max(),
    len(promo_engine.DISCOUNT_GRID_ALL)))

STOCK_SKUS = ["HX9911/09", "HX9911/88", "HX9914/63", "HX9911/94", "HX9911/27",
              "HX9911/84", "HX9911/79", "HX9992/02", "HX9992/44", "HX9914/54",
              "HX9918/89", "HX9917/88", "HX9917/90", "HX9992/45"]
PROXY_MAP = {"HX9911/88": "HX9911/89", "HX9992/02": "HX9992/11"}

# HX9911/89 and HX9992/11 serve double duty (stock proxy + their own Amazon ask).
# They sit in the stock group, since that is how they are being used here.
GROUP_STOCK = sorted({PROXY_MAP.get(s, s) for s in STOCK_SKUS})

GROUP_MENU = ["HX3603/01", "HX3673/11", "HX3673/14", "HX3792/11", "HX3792/12",
              "HX4023/02", "HX4023/03", "HX4033/21", "HX4034/21", "HX4034/22",
              "HX4044/41", "HX4044/52", "HX4046/41", "HX4046/52", "HX4072/41",
              "HX4072/42", "HX6322/04", "HX6352/11", "HX7101/01", "HX7108/04",
              "HX7110/02", "HX7113/01", "HX7119/01", "HX7400/02", "HX7406/02",
              "HX7420/08", "HX7421/08", "HX7429/01", "HX7429/03", "HX9914/61",
              "HX9914/62", "HX9917/89", "HX9992/12", "HX9992/43", "HY1200/25",
              "HY1200/26"]

print("Stock group: {} SKUs (no margin floor)".format(len(GROUP_STOCK)))
print("Menu group:  {} SKUs ({}% margin floor)".format(len(GROUP_MENU), MARGIN_FLOOR_MENU))


def run_group(skus, margin_floor, label):
    """Run one group and return (api_response, per_sku_weekly_dict)."""
    print("\n[{}] running {} SKUs, margin_floor={}...".format(label, len(skus), margin_floor))
    req = PlanRequest(
        skus=skus, plan_year=2026, base_year=2025, use_trend=True,
        objective="turnover", max_discount=0.40, budget_multiplier=1.0,
        ref_year=2025, unconstrained=True, alpha=None,
        margin_floor=margin_floor, economics="tn",
    )
    resp = run_plan(req)

    # run_common() returns portfolio-level qty only, so pull true per-SKU weekly
    # volumes/margins directly. The old gain-share approximation breaks when the
    # portfolio mixes premium handles with high-volume brush heads.
    sku_inputs = build_forecast_sku_inputs(skus, base_year=2025, use_trend=True, economics="tn")
    grid = promo_engine.DISCOUNT_GRID_ALL[promo_engine.DISCOUNT_GRID_ALL <= 0.401]
    base_results, opt_results, _cs, _ = run_portfolio(
        sku_inputs, grid, float("inf"), promo_engine.est_price_f,
        alpha=0.0, discount_bounds=compute_sku_quarterly_discount_bounds(tuple(skus)),
        margin_floor=margin_floor, quarter_budgets=None, economics="tn",
    )
    weekly = {}
    for sku, opt_df in opt_results.items():
        b = base_results[sku]
        weekly[sku] = {
            "group": label, "margin_floor": margin_floor,
            "week": [int(w) for w in opt_df["week"]],
            "discount": [float(x) for x in opt_df["discount"]],
            "qty_base": [float(x) for x in b["qty_base"]],
            "qty_promo": [float(x) for x in opt_df["qty_promo"]],
            "rev_base": [float(x) for x in b["rev_base"]],
            "rev_promo": [float(x) for x in opt_df["rev_promo"]],
            "profit_base": [float(x) for x in b["profit_base"]],
            "profit_promo": [float(x) for x in opt_df["profit_promo"]],
            "promo_spend": [float(x) for x in opt_df["promo_spend"]],
        }
    print("[{}] done — {} SKUs modelled".format(label, len(weekly)))
    return resp, weekly


resp_stock, weekly_stock = run_group(GROUP_STOCK, 0.0, "stock")
resp_menu, weekly_menu = run_group(GROUP_MENU, MARGIN_FLOOR_MENU, "menu")

merged = {
    "timeline": {**resp_stock["timeline"], **resp_menu["timeline"]},
    "sku_table": {r["sku"]: r for r in resp_stock["deep_dive"]["sku_table"]},
    "elasticity_per_sku": {**resp_stock["elasticity"]["per_sku"],
                           **resp_menu["elasticity"]["per_sku"]},
    "margin_floor_menu": MARGIN_FLOOR_MENU,
}
merged["sku_table"].update({r["sku"]: r for r in resp_menu["deep_dive"]["sku_table"]})

with open("hvse_combined.json", "w", encoding="utf-8") as f:
    json.dump(merged, f)
with open("hvse_weekly.json", "w", encoding="utf-8") as f:
    json.dump({**weekly_stock, **weekly_menu}, f)
print("\nSaved hvse_combined.json + hvse_weekly.json ({} SKUs total)".format(
    len(weekly_stock) + len(weekly_menu)))

# Average Price_base per SKU across Q4 2026 (W40-52) — single value per SKU, to
# line up against Amazon's static Local RRP column.
panel = data["panel_df"]
q4 = panel[(panel["Year"] == 2026) & (panel["Week"].between(40, 52))]
with open("hvse_base_price_q4.json", "w", encoding="utf-8") as f:
    json.dump(q4.groupby("SKU")["Price_base"].mean().round(2).to_dict(), f)
print("Saved hvse_base_price_q4.json")
