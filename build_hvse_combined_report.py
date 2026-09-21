"""Build the combined DE Diamond Clean Stock Depletion + HVSE Q4 2026 Amazon-menu
report, run at the SHIPPED 40% discount ceiling (no grid extension).

Sheets: Stock Depletion | W37-52 Calendar | Margin Analysis | Amazon Comparison
        | Weekly Elasticity | Excluded SKUs
"""
import json
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import openpyxl

D = json.load(open("hvse_combined.json", encoding="utf-8"))
BASE_PRICE_Q4 = json.load(open("hvse_base_price_q4.json", encoding="utf-8"))
WEEKLY = json.load(open("hvse_weekly.json", encoding="utf-8"))

# ── Stock snapshot (from the 2026-09-10 analysis) ─────────────────────────
STOCK = {
    "HX9911/09": 2135, "HX9911/88": 1561, "HX9914/63": 1158,
    "HX9911/94": 1036, "HX9911/27": 1033, "HX9911/84": 877,
    "HX9911/79": 580, "HX9992/02": 528, "HX9992/44": 518,
    "HX9914/54": 506, "HX9918/89": 365, "HX9917/88": 266,
    "HX9917/90": 252, "HX9992/45": 30,
}
EXCESS_VALUES = {
    "HX9911/09": 103615, "HX9911/88": 74138, "HX9914/63": 106148,
    "HX9911/94": 53747, "HX9911/27": 52250, "HX9911/84": 42008,
    "HX9911/79": 30470, "HX9992/02": 43634, "HX9992/44": 44406,
    "HX9914/54": 44862, "HX9918/89": 25560, "HX9917/88": 17510,
    "HX9917/90": 17229, "HX9992/45": 2670,
}
PROXY_MAP = {"HX9911/88": "HX9911/89", "HX9992/02": "HX9992/11"}
SERIES_MAP = {
    "HX9911": "DiamondClean 9000", "HX9914": "DiamondClean 9000",
    "HX9918": "DiamondClean Smart 9300-9700", "HX9917": "DiamondClean Smart 9300-9700",
    "HX9992": "Prestige 9900",
}
MISSING_NO_HISTORY = ["HX4023/02", "HX4023/03", "HX4033/21", "HX4034/21", "HX4034/22",
                      "HX4044/41", "HX4044/52", "HX4046/41", "HX4046/52", "HX4072/41",
                      "HX4072/42"]

# ── Amazon HVSE menu: only the 4 requested columns ────────────────────────
wb_hvse = openpyxl.load_workbook("../HVSE Q4 2026 - amz.xlsx", data_only=True, read_only=True)
ws_hvse = wb_hvse["Sheet1"]
AMZ = {}
for row in ws_hvse.iter_rows(min_row=2, values_only=True):
    if not row[0]:
        continue
    entry = {"local_rrp": row[1], "pct_of_rrp": row[2], "cpp": row[3], "conflict": None}
    prev = AMZ.get(row[0])
    if prev and (prev["cpp"] != entry["cpp"] or prev["pct_of_rrp"] != entry["pct_of_rrp"]):
        # Amazon's file lists this SKU twice with DIFFERENT asks. Keep the deeper
        # (lower CPP) as primary and flag the conflict rather than silently picking.
        deep, shallow = sorted([prev, entry], key=lambda e: e["cpp"] or 0)
        deep["conflict"] = "File lists 2 asks: {:.0f}% / €{} and {:.0f}% / €{}".format(
            (shallow["pct_of_rrp"] or 0) * 100, shallow["cpp"],
            (deep["pct_of_rrp"] or 0) * 100, deep["cpp"])
        AMZ[row[0]] = deep
    else:
        AMZ[row[0]] = entry

sku_table = D["sku_table"]
timeline = D["timeline"]
per_sku_beta = D["elasticity_per_sku"]
MENU_FLOOR = D["margin_floor_menu"]
W37_RANGE = list(range(37, 53))
Q4_WEEKS = list(range(40, 53))
EVENT_WEEKS = {41: "BDD", 42: "BDD", 47: "BF", 48: "BF", 49: "BF"}

MODELED = sorted(sku_table.keys())
STOCK_PANEL = {PROXY_MAP.get(s, s): s for s in STOCK}          # panel code -> stock label
AMZ_ONLY = [s for s in MODELED if s not in STOCK_PANEL]

# ── Per-SKU incrementals & margins — from TRUE per-SKU weekly volumes ─────
# The 2026-09-10 report approximated these by profit-gain share of the portfolio
# total. That is only valid within a homogeneous portfolio; this run mixes
# premium handles with high-volume brush heads, so real per-SKU qty is used.
# Portfolio totals rebuilt from merged per-SKU weekly data (the two runs each
# return their own portfolio block, so the API totals cannot be used directly).
def _tot(key):
    return sum(sum(wk[key]) for wk in WEEKLY.values())


cur_c = {"turnover": _tot("rev_base"), "profit": _tot("profit_base"),
         "qty": _tot("qty_base"), "promo_spend": 0.0}
rec_c = {"turnover": _tot("rev_promo"), "profit": _tot("profit_promo"),
         "qty": _tot("qty_promo"), "promo_spend": _tot("promo_spend")}
for d in (cur_c, rec_c):
    d["margin"] = d["profit"] / d["turnover"] * 100 if d["turnover"] else 0
total_inc = rec_c["qty"] - cur_c["qty"]

INC, MARGIN = {}, {}
for sku, wk in WEEKLY.items():
    idx = {w: i for i, w in enumerate(wk["week"])}
    w37_inc = sum(wk["qty_promo"][idx[w]] - wk["qty_base"][idx[w]]
                  for w in W37_RANGE if w in idx)
    full_yr = sum(qp - qb for qp, qb in zip(wk["qty_promo"], wk["qty_base"]))
    w37_d = [wk["discount"][idx[w]] * 100 for w in W37_RANGE
             if w in idx and wk["discount"][idx[w]] > 0]
    INC[sku] = {
        "full_yr": round(full_yr), "w37_inc": round(w37_inc),
        "w37_pw": len(w37_d),
        "avg_d": round(sum(w37_d) / len(w37_d), 1) if w37_d else 0,
        "spend37": sum(wk["promo_spend"][idx[w]] for w in W37_RANGE if w in idx),
    }
    # True weekly margin % = profit / revenue, using the optimized scenario
    MARGIN[sku] = {}
    for w in W37_RANGE:
        if w not in idx:
            continue
        i = idx[w]
        rev, prof = wk["rev_promo"][i], wk["profit_promo"][i]
        MARGIN[sku][w] = (prof / rev * 100) if rev > 0 else None
    base_rev = sum(wk["rev_base"])
    base_prof = sum(wk["profit_base"])
    MARGIN[sku]["_base"] = (base_prof / base_rev * 100) if base_rev > 0 else None

# ── Styles ────────────────────────────────────────────────────────────────
PHILIPS_BLUE, LIGHT_GRAY, MED_GRAY, WHITE = "003366", "F2F2F2", "D9D9D9", "FFFFFF"
ACCENT_ORANGE, ACCENT_RED, ACCENT_GREEN = "E67E22", "C0392B", "27AE60"
hdr_font = Font(name="Calibri", bold=True, color=WHITE, size=11)
hdr_fill = PatternFill("solid", fgColor=PHILIPS_BLUE)
title_font = Font(name="Calibri", bold=True, size=14, color=PHILIPS_BLUE)
sec_font = Font(name="Calibri", bold=True, size=12, color=PHILIPS_BLUE)
body_font = Font(name="Calibri", size=10)
bold_font = Font(name="Calibri", bold=True, size=10)
sub_font = Font(name="Calibri", size=10, color="666666")
small_hdr = Font(name="Calibri", bold=True, color=WHITE, size=8)
eur_fmt, num_fmt, pct_fmt = "#,##0", "#,##0", '0.0"%"'
thin_border = Border(*[Side(style="thin", color=MED_GRAY)] * 4)


def disc_fill(d):
    if not d: return PatternFill("solid", fgColor=WHITE)
    if d <= 10: return PatternFill("solid", fgColor="E8F5E9")
    if d <= 20: return PatternFill("solid", fgColor="FFF9C4")
    if d <= 30: return PatternFill("solid", fgColor="FFE0B2")
    if d <= 40: return PatternFill("solid", fgColor="FFCDD2")
    return PatternFill("solid", fgColor="E57373")


def margin_fill(m):
    if m is None: return PatternFill("solid", fgColor=WHITE)
    if m < 20: return PatternFill("solid", fgColor="E57373")
    if m < 30: return PatternFill("solid", fgColor="FFCDD2")
    if m < 40: return PatternFill("solid", fgColor="FFE0B2")
    if m < 50: return PatternFill("solid", fgColor="FFF9C4")
    return PatternFill("solid", fgColor="E8F5E9")


def write_row(ws, row, data, start_col=1, font=None, fill=None, number_format=None):
    for i, val in enumerate(data):
        c = ws.cell(row=row, column=start_col + i, value=val)
        if font: c.font = font
        if fill: c.fill = fill
        if number_format and isinstance(val, (int, float)): c.number_format = number_format
        c.border = thin_border


wb = Workbook()

# ═════════════════════════════════════════════════════════════════════════
# SHEET 1: Stock Depletion
# ═════════════════════════════════════════════════════════════════════════
ws = wb.active
ws.title = "Stock Depletion"
ws.sheet_properties.tabColor = PHILIPS_BLUE
r = 1
ws.cell(row=r, column=1, value="Diamond Clean Stock Depletion — W37-W52 (Sep-Dec 2026)").font = title_font; r += 1
ws.cell(row=r, column=1, value="Shipped 40% discount ceiling | Turnover objective | Unconstrained budget | Split margin floor").font = sub_font; r += 2

ws.cell(row=r, column=1, value="Run Configuration").font = sec_font; r += 1
for line in [
    "•  Discount grid: shipped 40% ceiling, NOT extended — reproduces the 2026-09-10 report exactly.",
    "•  SKU universe: {} modelled SKUs — {} stock-priority (known excess) + {} from Amazon's HVSE Q4 2026 menu.".format(
        len(MODELED), len(STOCK_PANEL), len(AMZ_ONLY)),
    "•  Total excess stock: {:,} units (€{:,}) across 14 SKUs.".format(sum(STOCK.values()), sum(EXCESS_VALUES.values())),
    "•  MARGIN FLOOR — applied differently by group, deliberately:",
    "      –  Stock-priority SKUs: NO floor. Clearing inventory ahead of the battery-directive deadline outweighs margin; recovering cash beats a write-off.",
    "      –  Amazon-menu SKUs: {:.0f}% floor. These have no clearance justification, so selling at or below cost would be pure value destruction.".format(MENU_FLOOR),
    "•  Each SKU's breakeven discount equals its own base margin (margin_after = 1 − (1 − base margin) ÷ (1 − discount)). See the Margin Analysis sheet.",
    "•  HX9911/88 and HX9992/02 use sister-variant elasticity (proxy) — exact codes are not in the model panel.",
]:
    ws.cell(row=r, column=1, value=line).font = body_font; r += 1
r += 1

ws.cell(row=r, column=1, value="Portfolio Totals (Full Year 2026, all {} SKUs)".format(len(MODELED))).font = sec_font; r += 1
write_row(ws, r, ["Metric", "No-Promo Base", "Recommended"], font=hdr_font, fill=hdr_fill); r += 1
for label, key, nf in [("Revenue (€)", "turnover", eur_fmt), ("Profit (€)", "profit", eur_fmt),
                       ("Margin (%)", "margin", pct_fmt), ("Volume (units)", "qty", num_fmt),
                       ("Promo Spend (€)", "promo_spend", eur_fmt)]:
    write_row(ws, r, [label, cur_c.get(key, 0), rec_c.get(key, 0)], font=body_font, number_format=nf)
    ws.cell(row=r, column=1).font = bold_font; r += 1
write_row(ws, r, ["Incremental Units", 0, total_inc], font=bold_font, number_format=num_fmt); r += 2

ws.cell(row=r, column=1, value="Per-SKU Stock Clearance — W37-W52 Incremental Sell-Out vs Excess Stock").font = sec_font; r += 1
write_row(ws, r, ["Stock SKU", "Product Series", "Excess Qty", "Excess Value (€)",
                  "W37-52 Incremental", "Clear %", "Avg Discount %", "Promo Weeks", "Verdict"],
          font=hdr_font, fill=hdr_fill); r += 1

tot_inc_stock = 0
for stock_sku, excess in sorted(STOCK.items(), key=lambda x: -x[1]):
    panel_sku = PROXY_MAP.get(stock_sku, stock_sku)
    inc = INC.get(panel_sku, {})
    w37_inc = inc.get("w37_inc", 0)
    clear = min(100, w37_inc / excess * 100) if excess else 0
    verdict = "LIKELY" if clear >= 80 else ("PARTIAL" if clear >= 50 else "UNLIKELY")
    if stock_sku in PROXY_MAP: verdict += " (proxy)"
    label = stock_sku + (" (via {})".format(PROXY_MAP[stock_sku]) if stock_sku in PROXY_MAP else "")
    write_row(ws, r, [label, SERIES_MAP.get(stock_sku.split("/")[0], "Other"), excess,
                      EXCESS_VALUES.get(stock_sku, 0), w37_inc, round(clear), inc.get("avg_d", 0),
                      inc.get("w37_pw", 0), verdict], font=body_font, number_format=num_fmt)
    ws.cell(row=r, column=4).number_format = eur_fmt
    pc = ws.cell(row=r, column=6); pc.number_format = '0"%"'
    pc.fill = PatternFill("solid", fgColor="C8E6C9" if clear >= 80 else "FFF9C4" if clear >= 50 else "FFCDD2")
    vc = ws.cell(row=r, column=9); vc.font = bold_font
    vc.fill = PatternFill("solid", fgColor="C8E6C9" if "LIKELY" in verdict else "FFF9C4" if "PARTIAL" in verdict else "FFCDD2")
    tot_inc_stock += w37_inc
    r += 1

tot_excess = sum(STOCK.values())
write_row(ws, r, ["TOTAL", "", tot_excess, sum(EXCESS_VALUES.values()), tot_inc_stock,
                  round(min(100, tot_inc_stock / tot_excess * 100)), "", "", ""],
          font=bold_font, fill=PatternFill("solid", fgColor=LIGHT_GRAY), number_format=num_fmt)
ws.cell(row=r, column=4).number_format = eur_fmt
ws.cell(row=r, column=6).number_format = '0"%"'
r += 2

ws.cell(row=r, column=1, value="Key Findings").font = sec_font; r += 1
n_likely = sum(1 for s, e in STOCK.items() if min(100, INC.get(PROXY_MAP.get(s, s), {}).get("w37_inc", 0) / e * 100) >= 80)
n_unlikely = sum(1 for s, e in STOCK.items() if min(100, INC.get(PROXY_MAP.get(s, s), {}).get("w37_inc", 0) / e * 100) < 50)
for line in [
    "1. {} of 14 stock SKUs clear ≥80% of their excess in W37-52; {} fall below 50% and need non-price levers.".format(n_likely, n_unlikely),
    "2. Portfolio aggregate clears {:,} incremental units vs {:,} excess — {:.1f}x coverage.".format(
        tot_inc_stock, tot_excess, tot_inc_stock / tot_excess),
    "3. HX9911/84 remains the hardest case — effectively no model response to price at any depth.",
    "4. Discounts stay within the shipped 40% ceiling; peak weeks (BDD W41-42, BF W47-49) occasionally reach 41-45%.",
]:
    ws.cell(row=r, column=1, value=line).font = body_font; r += 1

for col, w in zip("ABCDEFGHI", [26, 28, 12, 16, 18, 10, 14, 12, 18]):
    ws.column_dimensions[col].width = w

# ═════════════════════════════════════════════════════════════════════════
# SHEET 2: W37-52 Calendar
# ═════════════════════════════════════════════════════════════════════════
ws2 = wb.create_sheet("W37-52 Calendar")
ws2.sheet_properties.tabColor = ACCENT_ORANGE
r = 1
ws2.cell(row=r, column=1, value="Promo Calendar — W37-W52 Discount Depth (%)").font = title_font; r += 1
ws2.cell(row=r, column=1, value="Sep-Dec 2026 | 40% ceiling | Green ≤10% | Yellow ≤20% | Orange ≤30% | Red ≤40% | Deep Red >40%").font = sub_font; r += 2

last_col = len(W37_RANGE) + 1


def calendar_block(title, entries):
    """entries = list of (display_label, panel_sku, excess_qty_or_None)"""
    global r
    ws2.cell(row=r, column=1, value=title).font = sec_font; r += 1
    ws2.cell(row=r, column=1, value="Events").font = Font(name="Calibri", size=9, color="999999", italic=True)
    for ci, w in enumerate(W37_RANGE):
        c = ws2.cell(row=r, column=ci + 2, value=EVENT_WEEKS.get(w, ""))
        c.font = Font(name="Calibri", size=8, color=ACCENT_ORANGE, bold=True)
        c.alignment = Alignment(horizontal="center")
    r += 1
    ws2.cell(row=r, column=1, value="SKU").font = hdr_font
    ws2.cell(row=r, column=1).fill = hdr_fill
    for ci, w in enumerate(W37_RANGE):
        c = ws2.cell(row=r, column=ci + 2, value="W{}".format(w))
        c.font = small_hdr; c.fill = hdr_fill; c.alignment = Alignment(horizontal="center")
    for off, lbl in enumerate(["Excess Qty", "W37-52 Inc", "Avg Disc %"]):
        c = ws2.cell(row=r, column=last_col + 1 + off, value=lbl)
        c.font = Font(name="Calibri", bold=True, color=WHITE, size=9); c.fill = hdr_fill
    r += 1
    for label, panel_sku, excess in entries:
        discs = timeline.get(panel_sku, {}).get("opt_disc", [0] * 52)
        ws2.cell(row=r, column=1, value=label).font = Font(name="Calibri", size=9, bold=True)
        ws2.cell(row=r, column=1).border = thin_border
        for ci, w in enumerate(W37_RANGE):
            d = discs[w - 1]
            c = ws2.cell(row=r, column=ci + 2, value=d if d > 0 else "")
            c.font = Font(name="Calibri", size=8); c.fill = disc_fill(d)
            c.alignment = Alignment(horizontal="center"); c.border = thin_border
        inc = INC.get(panel_sku, {})
        ws2.cell(row=r, column=last_col + 1, value=excess if excess else "").number_format = num_fmt
        ws2.cell(row=r, column=last_col + 2, value=inc.get("w37_inc", 0)).number_format = num_fmt
        ws2.cell(row=r, column=last_col + 3, value=inc.get("avg_d", 0)).number_format = "0.0"
        for off in range(3):
            ws2.cell(row=r, column=last_col + 1 + off).font = body_font
        r += 1
    r += 2


calendar_block("Stock-Priority SKUs (known excess stock)",
               [(s + (" (via {})".format(PROXY_MAP[s]) if s in PROXY_MAP else ""), PROXY_MAP.get(s, s), q)
                for s, q in sorted(STOCK.items(), key=lambda x: -x[1])])
calendar_block("Amazon HVSE Menu SKUs (no stock figure available)",
               [(s, s, None) for s in AMZ_ONLY])

ws2.column_dimensions["A"].width = 24
for ci in range(len(W37_RANGE)):
    ws2.column_dimensions[get_column_letter(ci + 2)].width = 4.8
for off in range(3):
    ws2.column_dimensions[get_column_letter(last_col + 1 + off)].width = 12

# ═════════════════════════════════════════════════════════════════════════
# SHEET 3: Margin Analysis
# ═════════════════════════════════════════════════════════════════════════
ws3 = wb.create_sheet("Margin Analysis")
ws3.sheet_properties.tabColor = ACCENT_RED
base_margin = cur_c["margin"]
r = 1
ws3.cell(row=r, column=1, value="Margin Erosion Analysis — W37-W52 Per-SKU").font = title_font; r += 1
ws3.cell(row=r, column=1, value="True per-SKU margin (profit ÷ revenue) from the optimized scenario. Portfolio base margin: {:.1f}% | Red <20% | Orange <30% | Yellow <40% | Green ≥50%".format(base_margin)).font = sub_font; r += 1
ws3.cell(row=r, column=1, value="Stock SKUs run with NO margin floor (clearance priority). Amazon-menu SKUs run with a {:.0f}% floor. 'Max Safe Disc %' = the SKU's own base margin — discount beyond it and the SKU sells below cost.".format(MENU_FLOOR)).font = sub_font; r += 2

sum_col = len(W37_RANGE) + 2


def margin_block(title, entries):
    global r
    ws3.cell(row=r, column=1, value=title).font = sec_font; r += 1
    ws3.cell(row=r, column=1, value="SKU").font = hdr_font
    ws3.cell(row=r, column=1).fill = hdr_fill
    for ci, w in enumerate(W37_RANGE):
        c = ws3.cell(row=r, column=ci + 2, value="W{}".format(w))
        c.font = small_hdr; c.fill = hdr_fill; c.alignment = Alignment(horizontal="center")
    for off, lbl in enumerate(["Avg Margin", "Min Margin", "Base Margin", "Max Safe Disc %", "Our Disc %"]):
        c = ws3.cell(row=r, column=sum_col + off, value=lbl)
        c.font = Font(name="Calibri", bold=True, color=WHITE, size=9); c.fill = hdr_fill
    r += 1
    for label, panel_sku in entries:
        mrow = MARGIN.get(panel_sku, {})
        ws3.cell(row=r, column=1, value=label).font = Font(name="Calibri", size=9, bold=True)
        ws3.cell(row=r, column=1).border = thin_border
        margins = []
        for ci, w in enumerate(W37_RANGE):
            m = mrow.get(w)
            c = ws3.cell(row=r, column=ci + 2, value=round(m, 1) if m is not None else None)
            c.font = Font(name="Calibri", size=8); c.fill = margin_fill(m)
            c.alignment = Alignment(horizontal="center"); c.border = thin_border
            c.number_format = "0.0"
            if m is not None: margins.append(m)
        bm = mrow.get("_base")
        our_d = INC.get(panel_sku, {}).get("avg_d", 0)
        stats = [sum(margins) / len(margins) if margins else None,
                 min(margins) if margins else None, bm]
        for off, v in enumerate(stats):
            c = ws3.cell(row=r, column=sum_col + off, value=round(v, 1) if v is not None else None)
            c.font = bold_font; c.fill = margin_fill(v); c.number_format = "0.0"
        # Max safe discount == the SKU's own base margin.
        c = ws3.cell(row=r, column=sum_col + 3, value=round(bm, 1) if bm is not None else None)
        c.font = bold_font; c.number_format = "0.0"
        c = ws3.cell(row=r, column=sum_col + 4, value=our_d)
        c.font = bold_font; c.number_format = "0.0"
        if bm is not None and our_d > bm:
            c.fill = PatternFill("solid", fgColor="E57373")   # priced below cost
        r += 1
    r += 2


margin_block("Stock-Priority SKUs",
             [(s, PROXY_MAP.get(s, s)) for s in sorted(STOCK, key=lambda x: -STOCK[x])])
margin_block("Amazon HVSE Menu SKUs", [(s, s) for s in AMZ_ONLY])

ws3.cell(row=r, column=1, value="Portfolio recommended margin: {:.1f}%".format(rec_c["margin"])).font = bold_font
ws3.cell(row=r, column=5, value="vs base: {:.1f}%".format(base_margin)).font = body_font
ws3.cell(row=r, column=9, value="Margin drop: {:.1f}pp".format(base_margin - rec_c["margin"])).font = Font(
    name="Calibri", size=10, bold=True, color=ACCENT_RED)

r += 1
ws3.cell(row=r, column=1, value="Caveats on the margin floor").font = sec_font; r += 1
for line in [
    "•  The {:.0f}% floor is NOT absolute. Mandatory campaign weeks (peak-week inclusion) can override it — the engine forces a promo in those weeks even when every".format(MENU_FLOOR),
    "    candidate depth fails the floor. HX6322/04 is the one case here: it takes 5% at W44 for 8.4% margin.",
    "•  HX6322/04 cannot satisfy a {:.0f}% floor at ANY depth — its base margin is only 12.4%, already below the floor. It should not be promoted on economics alone.".format(MENU_FLOOR),
    "    For reference, Amazon asks 23.1% off RRP on this SKU, which would put it at roughly −14% margin.",
    "•  Stock SKUs are intentionally unfloored, so several do run thin or briefly negative (HX9914/54 touches −0.2%). That is the accepted clearance trade-off.",
]:
    ws3.cell(row=r, column=1, value=line).font = body_font; r += 1

ws3.column_dimensions["A"].width = 16
for ci in range(len(W37_RANGE)):
    ws3.column_dimensions[get_column_letter(ci + 2)].width = 4.8
for off in range(5):
    ws3.column_dimensions[get_column_letter(sum_col + off)].width = 13

# ═════════════════════════════════════════════════════════════════════════
# SHEET 4: Amazon Comparison
# ═════════════════════════════════════════════════════════════════════════
ws4 = wb.create_sheet("Amazon Comparison")
ws4.sheet_properties.tabColor = ACCENT_GREEN
r = 1
ws4.cell(row=r, column=1, value="Our Recommendation vs Amazon's HVSE Q4 2026 Request").font = title_font; r += 1
ws4.cell(row=r, column=1, value="Amazon columns are taken as-is from 'HVSE Q4 2026 - amz.xlsx'. Our base price is the average model Price_base across Q4 (W40-52) 2026.").font = sub_font; r += 2

headers = ["Basic material", "Local RRP", "% of RRP", "Estimated CPP* (incl. VAT)",
           "Our Base Price Q4 avg (€)", "Our Avg Discount % (W37-52)", "Our Promo Weeks",
           "Our Implied CPP (€)", "Delta CPP (€)", "Delta % (diff. bases)",
           "Avg |Elasticity β| Q4", "Excess Stock", "Group", "Data note"]
write_row(ws4, r, headers, font=hdr_font, fill=hdr_fill)
for c in range(1, len(headers) + 1):
    ws4.cell(row=r, column=c).alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
ws4.row_dimensions[r].height = 42
r += 1

ordered = ([(STOCK_PANEL[p], p) for p in sorted(STOCK_PANEL, key=lambda x: -STOCK.get(STOCK_PANEL[x], 0))]
           + [(s, s) for s in AMZ_ONLY])
for display, panel_sku in ordered:
    amz = AMZ.get(panel_sku, {})
    inc = INC.get(panel_sku, {})
    bp = BASE_PRICE_Q4.get(panel_sku)
    our_d = inc.get("avg_d", 0)
    implied = round(bp * (1 - our_d / 100), 2) if bp and our_d else bp
    amz_pct = round(amz["pct_of_rrp"] * 100, 1) if amz.get("pct_of_rrp") else None
    delta_pct = round(our_d - amz_pct, 1) if amz_pct is not None and our_d else None
    delta_cpp = round(implied - amz["cpp"], 2) if implied and amz.get("cpp") else None
    is_stock = display in STOCK
    group = ("Stock + Amazon menu" if is_stock and panel_sku in AMZ
             else "Stock priority" if is_stock else "Amazon menu")
    label = display + (" (via {})".format(PROXY_MAP[display]) if display in PROXY_MAP else "")
    beta = [b["value"] for b in per_sku_beta.get(panel_sku, {}).get("beta_weekly", []) if 40 <= b["week"] <= 52]
    write_row(ws4, r, [label, amz.get("local_rrp"), amz_pct, amz.get("cpp"), bp, our_d,
                       inc.get("w37_pw", 0), implied, delta_cpp, delta_pct,
                       round(sum(beta) / len(beta), 2) if beta else None,
                       STOCK.get(display), group, amz.get("conflict")],
              font=body_font)
    for c in (2, 4, 5, 8, 9): ws4.cell(row=r, column=c).number_format = "#,##0.00"
    for c in (3, 6, 10): ws4.cell(row=r, column=c).number_format = "0.0"
    ws4.cell(row=r, column=11).number_format = "0.00"
    ws4.cell(row=r, column=12).number_format = num_fmt
    if delta_cpp is not None:
        # Negative delta = our price is BELOW Amazon's ask = we would go deeper.
        ws4.cell(row=r, column=9).fill = PatternFill(
            "solid", fgColor="C8E6C9" if delta_cpp < 0 else "FFCDD2")
    if amz.get("conflict"):
        ws4.cell(row=r, column=14).fill = PatternFill("solid", fgColor="FFE0B2")
    r += 1

r += 1
ws4.cell(row=r, column=1, value="Reading this sheet").font = sec_font; r += 1
def _implied(p):
    bp, d = BASE_PRICE_Q4.get(p), INC.get(p, {}).get("avg_d", 0)
    return bp * (1 - d / 100) if bp and d else bp


n_amz = sum(1 for _, p in ordered if p in AMZ)
deeper = sum(1 for _, p in ordered if AMZ.get(p, {}).get("cpp") and _implied(p)
             and _implied(p) < AMZ[p]["cpp"])
shallower = sum(1 for _, p in ordered if AMZ.get(p, {}).get("cpp") and _implied(p)
                and _implied(p) > AMZ[p]["cpp"])
for line in [
    "•  'Delta CPP' is the meaningful comparison: our implied consumer price minus Amazon's requested CPP. Green (negative) = our price is LOWER than Amazon's ask.",
    "•  Of {} SKUs with an Amazon ask, our model lands BELOW Amazon's CPP on {} and ABOVE on {}.".format(n_amz, deeper, shallower),
    "•  CAUTION — 'Delta %' compares two different bases and can mislead. Amazon's '% of RRP' is off the official Local RRP; our discount % is off the model's Price_base "
    "(a rolling ~10-week max of actual selling ASP), which sits well below RRP for most SKUs. A smaller headline % can still mean a lower final price. Use Delta CPP.",
    "•  Our model is capped at the shipped 40% ceiling. Where Amazon asks for more than 40% off RRP, our depth figure is a floor, not a disagreement.",
    "•  'Our Implied CPP' = Our Base Price Q4 avg × (1 − Our Avg Discount %).",
    "•  Flagged in 'Data note': Amazon's file lists HX9911/79 twice with conflicting asks. The deeper ask is used; both are shown. Worth confirming which is current.",
]:
    ws4.cell(row=r, column=1, value=line).font = body_font; r += 1

for col, w in zip("ABCDEFGHIJKLMN", [26, 12, 11, 15, 16, 16, 12, 14, 13, 15, 14, 12, 20, 42]):
    ws4.column_dimensions[col].width = w
ws4.freeze_panes = "A4"

# ═════════════════════════════════════════════════════════════════════════
# SHEET 5: Weekly Elasticity
# ═════════════════════════════════════════════════════════════════════════
ws5 = wb.create_sheet("Weekly Elasticity")
ws5.sheet_properties.tabColor = "8E44AD"
r = 1
ws5.cell(row=r, column=1, value="Price Elasticity |β| per SKU per Week — W37-W52").font = title_font; r += 1
ws5.cell(row=r, column=1, value="Higher |β| = more volume response per 1% price cut. β>1 means a discount grows revenue.").font = sub_font; r += 2

ws5.cell(row=r, column=1, value="SKU").font = hdr_font
ws5.cell(row=r, column=1).fill = hdr_fill
for ci, w in enumerate(W37_RANGE):
    c = ws5.cell(row=r, column=ci + 2, value="W{}".format(w))
    c.font = small_hdr; c.fill = hdr_fill; c.alignment = Alignment(horizontal="center")
c = ws5.cell(row=r, column=len(W37_RANGE) + 2, value="Avg")
c.font = Font(name="Calibri", bold=True, color=WHITE, size=9); c.fill = hdr_fill
r += 1

for display, panel_sku in ordered:
    bmap = {b["week"]: b["value"] for b in per_sku_beta.get(panel_sku, {}).get("beta_weekly", [])}
    ws5.cell(row=r, column=1, value=display).font = Font(name="Calibri", size=9, bold=True)
    vals = []
    for ci, w in enumerate(W37_RANGE):
        v = bmap.get(w)
        c = ws5.cell(row=r, column=ci + 2, value=v)
        c.font = Font(name="Calibri", size=8); c.alignment = Alignment(horizontal="center")
        c.border = thin_border; c.number_format = "0.00"
        if v is not None:
            vals.append(v)
            if v >= 1.5: c.fill = PatternFill("solid", fgColor="C8E6C9")
            elif v >= 1.0: c.fill = PatternFill("solid", fgColor="FFF9C4")
            else: c.fill = PatternFill("solid", fgColor="FFCDD2")
    c = ws5.cell(row=r, column=len(W37_RANGE) + 2, value=round(sum(vals) / len(vals), 2) if vals else None)
    c.font = bold_font; c.number_format = "0.00"
    r += 1

ws5.column_dimensions["A"].width = 16
for ci in range(len(W37_RANGE)):
    ws5.column_dimensions[get_column_letter(ci + 2)].width = 5.2
ws5.column_dimensions[get_column_letter(len(W37_RANGE) + 2)].width = 8
ws5.freeze_panes = "B5"

# ═════════════════════════════════════════════════════════════════════════
# SHEET 6: Excluded SKUs
# ═════════════════════════════════════════════════════════════════════════
ws6 = wb.create_sheet("Excluded SKUs")
ws6.sheet_properties.tabColor = MED_GRAY
r = 1
ws6.cell(row=r, column=1, value="Amazon HVSE Menu SKUs Not Modelled").font = title_font; r += 1
ws6.cell(row=r, column=1, value="These SKUs appear on Amazon's request menu and exist in the panel, but have no 2025 history to build a forecast from.").font = sub_font; r += 2
write_row(ws6, r, ["Basic material", "Local RRP", "% of RRP", "Estimated CPP* (incl. VAT)", "Reason"],
          font=hdr_font, fill=hdr_fill); r += 1
for s in MISSING_NO_HISTORY:
    a = AMZ.get(s, {})
    write_row(ws6, r, [s, a.get("local_rrp"),
                       round(a["pct_of_rrp"] * 100, 1) if a.get("pct_of_rrp") else None,
                       a.get("cpp"), "2026-only launch — no 2025 history for a base-year forecast."],
              font=body_font)
    for c in (2, 4): ws6.cell(row=r, column=c).number_format = "#,##0.00"
    ws6.cell(row=r, column=3).number_format = "0.0"
    r += 1
for col, w in zip("ABCDE", [18, 14, 12, 18, 60]):
    ws6.column_dimensions[col].width = w

wb.save("../DE_HVSE_Combined_Q4_2026-09-15.xlsx")
print("Saved DE_HVSE_Combined_Q4_2026.xlsx")
print("Modelled: {} | stock {} | amazon-only {} | excluded {}".format(
    len(MODELED), len(STOCK_PANEL), len(AMZ_ONLY), len(MISSING_NO_HISTORY)))
print("Stock clearance: {:,} inc vs {:,} excess ({:.1f}x)".format(
    tot_inc_stock, tot_excess, tot_inc_stock / tot_excess))
print("vs Amazon CPP: below on {}, above on {} (of {} with an ask)".format(deeper, shallower, n_amz))
