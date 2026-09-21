"""Build the Diamond Clean Stock Depletion Scenario Analysis Excel report."""
import json, os
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import LineChart, BarChart, Reference

# ── Load data ──────────────────────────────────────────────
D = {}
for key in ["S1", "S2", "S3"]:
    with open("stock_{}.json".format(key), encoding="utf-8") as f:
        D[key] = json.load(f)

ALL_MODEL_SKUS = list(D["S1"]["timeline"].keys())
WEEKS = list(range(1, 53))
W37_52 = list(range(36, 52))  # 0-based indices for W37-W52

# Stock snapshot
STOCK = {
    "HX9911/09": 2135, "HX9911/88": 1561, "HX9914/63": 1158,
    "HX9911/94": 1036, "HX9911/27": 1033, "HX9911/84": 877,
    "HX9911/79": 580, "HX9992/02": 528, "HX9992/44": 518,
    "HX9914/54": 506, "HX9918/89": 365, "HX9917/88": 266,
    "HX9917/90": 252, "HX9944/13": 119, "HX9992/45": 30,
    "HX9913/18": 28,
}

PROXY_MAP = {"HX9911/88": "HX9911/89", "HX9992/02": "HX9992/11"}
DROPPED = {"HX9944/13", "HX9913/18"}

SC_NAMES = {
    "S1": "S1: Full Clearance (50% max, unconstrained)",
    "S2": "S2: Moderate Depth (35% max, unconstrained)",
    "S3": "S3: Budget-Constrained (50% max, 1x budget, 2025 Q-pattern)",
}
SC_SHORT = {"S1": "S1: Full Clear", "S2": "S2: Moderate", "S3": "S3: Constrained"}

# ── Styles ─────────────────────────────────────────────────
PHILIPS_BLUE = "003366"
PHILIPS_LIGHT = "D6E4F0"
ACCENT_GREEN = "27AE60"
ACCENT_ORANGE = "E67E22"
ACCENT_RED = "C0392B"
LIGHT_GRAY = "F2F2F2"
MED_GRAY = "D9D9D9"
WHITE = "FFFFFF"

hdr_font = Font(name="Calibri", bold=True, color=WHITE, size=11)
hdr_fill = PatternFill("solid", fgColor=PHILIPS_BLUE)
title_font = Font(name="Calibri", bold=True, size=14, color=PHILIPS_BLUE)
sec_font = Font(name="Calibri", bold=True, size=12, color=PHILIPS_BLUE)
body_font = Font(name="Calibri", size=10)
bold_font = Font(name="Calibri", bold=True, size=10)
eur_fmt = "#,##0"
num_fmt = "#,##0"
pct_fmt = '0.0"%"'
thin_border = Border(
    left=Side(style="thin", color=MED_GRAY), right=Side(style="thin", color=MED_GRAY),
    top=Side(style="thin", color=MED_GRAY), bottom=Side(style="thin", color=MED_GRAY),
)

def write_row(ws, row, data, start_col=1, font=None, fill=None, number_format=None):
    for i, val in enumerate(data):
        cell = ws.cell(row=row, column=start_col+i, value=val)
        if font: cell.font = font
        if fill: cell.fill = fill
        if number_format and isinstance(val, (int, float)): cell.number_format = number_format
        cell.border = thin_border

def disc_fill(d):
    if d == 0 or d is None: return PatternFill("solid", fgColor=WHITE)
    if d <= 10: return PatternFill("solid", fgColor="E8F5E9")
    if d <= 20: return PatternFill("solid", fgColor="FFF9C4")
    if d <= 30: return PatternFill("solid", fgColor="FFE0B2")
    if d <= 40: return PatternFill("solid", fgColor="FFCDD2")
    return PatternFill("solid", fgColor="E57373")  # deep red for >40%

def verdict_fill(v):
    if v == "LIKELY": return PatternFill("solid", fgColor="C8E6C9")
    if v == "PARTIAL": return PatternFill("solid", fgColor="FFF9C4")
    return PatternFill("solid", fgColor="FFCDD2")

def margin_fill(m):
    if m is None: return PatternFill("solid", fgColor=WHITE)
    if m < 20: return PatternFill("solid", fgColor="E57373")
    if m < 30: return PatternFill("solid", fgColor="FFCDD2")
    if m < 40: return PatternFill("solid", fgColor="FFE0B2")
    if m < 50: return PatternFill("solid", fgColor="FFF9C4")
    return PatternFill("solid", fgColor="E8F5E9")


# ── Helper: compute per-SKU incremental units ──
def compute_sku_incrementals(sc_key):
    data = D[sc_key]
    rec = data["compare"]["recommended"]
    cur = data["compare"]["current"]
    total_inc = rec["qty"] - cur["qty"]
    st = data["deep_dive"]["sku_table"]
    total_gain = sum(s["gain"] for s in st)
    result = {}
    for s in st:
        share = s["gain"] / total_gain if total_gain > 0 else 0
        full_yr = round(total_inc * share)
        discs = data["timeline"][s["sku"]]["opt_disc"]
        total_pw = sum(1 for d in discs if d > 0)
        w37_pw = sum(1 for i in W37_52 if i < len(discs) and discs[i] > 0)
        w37_share = w37_pw / total_pw if total_pw > 0 else 0
        w37_inc = round(full_yr * w37_share)
        w37_discs = [discs[i] for i in W37_52 if i < len(discs) and discs[i] > 0]
        avg_d = sum(w37_discs) / len(w37_discs) if w37_discs else 0
        result[s["sku"]] = {"full_yr": full_yr, "w37_inc": w37_inc, "avg_d": avg_d, "w37_pw": w37_pw}
    return result


wb = Workbook()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SHEET 1: Stock Depletion Feasibility
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ws = wb.active
ws.title = "Stock Depletion"
ws.sheet_properties.tabColor = PHILIPS_BLUE

r = 1
ws.cell(row=r, column=1, value="Diamond Clean Stock Depletion Feasibility \u2014 W37-W52 (Sep-Dec 2026)").font = title_font; r += 1
ws.cell(row=r, column=1, value="Can we clear the excess stock through promotional sell-out in the remaining 16 weeks?").font = Font(name="Calibri", size=11, color="666666"); r += 2

# Context
ws.cell(row=r, column=1, value="Stock Situation").font = sec_font; r += 1
ws.cell(row=r, column=1, value="\u2022  Total excess stock: 10,992 units (\u20ac667,838) projected at 28 Dec 2026").font = body_font; r += 1
ws.cell(row=r, column=1, value="\u2022  16 SKUs across DiamondClean 9000, Prestige 9900, and DiamondClean Smart series").font = body_font; r += 1
ws.cell(row=r, column=1, value="\u2022  Model coverage: 14 SKUs (12 direct + 2 proxied), covering 10,845 of 10,992 units (99%)").font = body_font; r += 1
ws.cell(row=r, column=1, value="\u2022  Priority: Stock clearance over margin preservation \u2014 all scenarios unconstrained, no margin floor").font = body_font; r += 2

# Scenario definitions
ws.cell(row=r, column=1, value="Scenarios").font = sec_font; r += 1
sc_defs = [
    ("S1: Full Clearance", "Max 50% discount | Unconstrained budget | Turnover objective", "Maximum promotional pressure to clear as much as possible"),
    ("S2: Moderate Depth", "Max 35% discount | Unconstrained budget | Turnover objective", "Avoids the >40% territory flagged as over-discounting at Prime Day"),
    ("S3: Budget-Constrained", "Max 50% discount | 1x historical budget | Q-split: 12/13/21/54", "Same depth allowance as S1, but limited to historical spend levels"),
]
write_row(ws, r, ["Scenario", "Parameters", "Rationale"], font=hdr_font, fill=hdr_fill); r += 1
for name, params, rationale in sc_defs:
    write_row(ws, r, [name, params, rationale], font=body_font); r += 1
r += 1

# Portfolio comparison
ws.cell(row=r, column=1, value="Portfolio Comparison (Full Year 2026)").font = sec_font; r += 1
cur = D["S1"]["compare"]["current"]
write_row(ws, r, ["Metric", "No-Promo Base", "S1: Full Clear", "S2: Moderate", "S3: Constrained"], font=hdr_font, fill=hdr_fill); r += 1
metrics = [
    ("Revenue (\u20ac)", "turnover", eur_fmt),
    ("Profit (\u20ac)", "profit", eur_fmt),
    ("Margin (%)", "margin", pct_fmt),
    ("Volume (units)", "qty", num_fmt),
    ("Incremental Units", None, num_fmt),
    ("Promo Spend (\u20ac)", "promo_spend", eur_fmt),
]
for label, key, nf in metrics:
    if key == "margin":
        vals = [label, cur[key]] + [D[sc]["compare"]["recommended"][key] for sc in ["S1","S2","S3"]]
    elif key is None:  # incremental
        vals = [label, 0] + [D[sc]["compare"]["recommended"]["qty"] - cur["qty"] for sc in ["S1","S2","S3"]]
    else:
        vals = [label, cur.get(key, 0)] + [D[sc]["compare"]["recommended"].get(key, 0) for sc in ["S1","S2","S3"]]
    write_row(ws, r, vals, font=body_font, number_format=nf)
    ws.cell(row=r, column=1).font = bold_font
    r += 1
r += 1

# === THE KEY TABLE: Per-SKU Stock Clearance Feasibility ===
ws.cell(row=r, column=1, value="Per-SKU Stock Clearance \u2014 W37-W52 Incremental Sell-Out vs Excess Stock").font = sec_font; r += 1

headers = ["Stock SKU", "Product Series", "Excess Qty", "Excess Value (\u20ac)"]
for sc in ["S1", "S2", "S3"]:
    headers.extend(["{} W37-52 Inc".format(SC_SHORT[sc]), "{} Clear%".format(SC_SHORT[sc])])
headers.append("Best Verdict")
write_row(ws, r, headers, font=hdr_font, fill=hdr_fill); r += 1

# Product series mapping
series_map = {
    "HX9911": "DiamondClean 9000", "HX9914": "DiamondClean 9000",
    "HX9913": "DiamondClean 9000", "HX9918": "DiamondClean Smart 9300-9700",
    "HX9917": "DiamondClean Smart 9300-9700", "HX9992": "Prestige 9900",
    "HX9944": "DiamondClean Smart 9300-9700",
}
# Excess value (approximate from snapshot)
excess_values = {
    "HX9911/09": 103615, "HX9911/88": 74138, "HX9914/63": 106148,
    "HX9911/94": 53747, "HX9911/27": 52250, "HX9911/84": 42008,
    "HX9911/79": 30470, "HX9992/02": 43634, "HX9992/44": 44406,
    "HX9914/54": 44862, "HX9918/89": 25560, "HX9917/88": 17510,
    "HX9917/90": 17229, "HX9944/13": 8190, "HX9992/45": 2670,
    "HX9913/18": 1402,
}

# Pre-compute incrementals
all_inc = {sc: compute_sku_incrementals(sc) for sc in ["S1", "S2", "S3"]}

total_excess = 0
total_w37 = {"S1": 0, "S2": 0, "S3": 0}

for stock_sku, excess_qty in sorted(STOCK.items(), key=lambda x: -x[1]):
    prefix = stock_sku.split("/")[0]
    series = series_map.get(prefix, "Other")
    ev = excess_values.get(stock_sku, 0)

    if stock_sku in DROPPED:
        vals = [stock_sku, series, excess_qty, ev, "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "NO MODEL"]
        write_row(ws, r, vals, font=body_font, number_format=eur_fmt)
        ws.cell(row=r, column=11).fill = PatternFill("solid", fgColor=MED_GRAY)
        r += 1
        total_excess += excess_qty
        continue

    model_sku = PROXY_MAP.get(stock_sku, stock_sku)
    row_vals = [stock_sku, series, excess_qty, ev]

    best_pct = 0
    for sc in ["S1", "S2", "S3"]:
        inc_data = all_inc[sc].get(model_sku, {"w37_inc": 0})
        w37_inc = inc_data["w37_inc"]
        clear_pct = min(100, w37_inc / excess_qty * 100) if excess_qty > 0 else 0
        best_pct = max(best_pct, clear_pct)
        row_vals.extend([w37_inc, round(clear_pct, 0)])
        total_w37[sc] += w37_inc

    verdict = "LIKELY" if best_pct >= 80 else ("PARTIAL" if best_pct >= 50 else "UNLIKELY")
    if stock_sku in PROXY_MAP:
        verdict += " (proxy)"
    row_vals.append(verdict)

    write_row(ws, r, row_vals, font=body_font, number_format=num_fmt)
    ws.cell(row=r, column=4).number_format = eur_fmt
    # Color the clearance % cells
    for col_offset, sc in enumerate(["S1", "S2", "S3"]):
        pct_col = 6 + col_offset * 2
        cell = ws.cell(row=r, column=pct_col)
        cell.number_format = '0"%"'
        pct_val = cell.value
        if isinstance(pct_val, (int, float)):
            if pct_val >= 80: cell.fill = PatternFill("solid", fgColor="C8E6C9")
            elif pct_val >= 50: cell.fill = PatternFill("solid", fgColor="FFF9C4")
            else: cell.fill = PatternFill("solid", fgColor="FFCDD2")
    # Verdict cell
    v_cell = ws.cell(row=r, column=11)
    if "LIKELY" in str(v_cell.value): v_cell.fill = PatternFill("solid", fgColor="C8E6C9")
    elif "PARTIAL" in str(v_cell.value): v_cell.fill = PatternFill("solid", fgColor="FFF9C4")
    else: v_cell.fill = PatternFill("solid", fgColor="FFCDD2")
    v_cell.font = bold_font

    total_excess += excess_qty
    r += 1

# Total row
total_row = ["TOTAL", "", sum(STOCK.values()), sum(excess_values.values())]
for sc in ["S1", "S2", "S3"]:
    total_clear = min(100, total_w37[sc] / total_excess * 100)
    total_row.extend([total_w37[sc], round(total_clear, 0)])
total_row.append("")
write_row(ws, r, total_row, font=bold_font, fill=PatternFill("solid", fgColor=LIGHT_GRAY), number_format=num_fmt)
ws.cell(row=r, column=4).number_format = eur_fmt
r += 2

# Key insights
ws.cell(row=r, column=1, value="Key Findings").font = sec_font; r += 1
findings = [
    "1. All three scenarios clear the total 10,992 units in aggregate \u2014 the portfolio has enough demand.",
    "2. HX9911/84 shows zero incremental in all scenarios \u2014 this SKU may need channel-specific action (bundling, outlet).",
    "3. HX9992/44, HX9917/90 are difficult to clear via price alone \u2014 low model response, consider non-price levers.",
    "4. S1 (50% max) vs S2 (35% max) difference is ~16K incremental units \u2014 the extra 15pp depth adds meaningful volume.",
    "5. S3 shows that constraining budget sharply reduces clearance of lower-priority SKUs while protecting the top movers.",
    "6. Proxy SKUs (HX9911/88, HX9992/02) use sister-variant elasticity \u2014 directionally correct but actual response may differ.",
]
for f in findings:
    ws.cell(row=r, column=1, value=f).font = body_font; r += 1

# Column widths
ws.column_dimensions["A"].width = 14
ws.column_dimensions["B"].width = 28
ws.column_dimensions["C"].width = 12
ws.column_dimensions["D"].width = 16
for c_idx in range(5, 12):
    ws.column_dimensions[get_column_letter(c_idx)].width = 16

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SHEET 2: W37-52 Calendar
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ws2 = wb.create_sheet("W37-52 Calendar")
ws2.sheet_properties.tabColor = "E67E22"

r = 1
ws2.cell(row=r, column=1, value="Promo Calendar \u2014 W37-W52 Discount Depth (%)").font = title_font; r += 1
ws2.cell(row=r, column=1, value="Sep-Dec 2026 | Mapped to stock SKUs | Green \u226410% | Yellow \u226420% | Orange \u226430% | Red \u226440% | Deep Red >40%").font = Font(name="Calibri", size=10, color="666666"); r += 2

event_weeks_w37 = {41: "BDD", 42: "BDD", 47: "BF", 48: "BF", 49: "BF"}
w37_range = list(range(37, 53))

for sc, sc_name in [("S1", SC_NAMES["S1"]), ("S2", SC_NAMES["S2"]), ("S3", SC_NAMES["S3"])]:
    ws2.cell(row=r, column=1, value=sc_name).font = sec_font; r += 1

    # Event markers
    ws2.cell(row=r, column=1, value="Events").font = Font(name="Calibri", size=9, color="999999", italic=True)
    for ci, w in enumerate(w37_range):
        cell = ws2.cell(row=r, column=ci+2, value=event_weeks_w37.get(w, ""))
        cell.font = Font(name="Calibri", size=8, color=ACCENT_ORANGE, bold=True)
        cell.alignment = Alignment(horizontal="center")
    r += 1

    # Header
    ws2.cell(row=r, column=1, value="Stock SKU").font = hdr_font
    ws2.cell(row=r, column=1).fill = hdr_fill
    excess_col = len(w37_range) + 2
    for ci, w in enumerate(w37_range):
        cell = ws2.cell(row=r, column=ci+2, value="W{}".format(w))
        cell.font = Font(name="Calibri", bold=True, color=WHITE, size=8)
        cell.fill = hdr_fill
        cell.alignment = Alignment(horizontal="center")
    cell = ws2.cell(row=r, column=excess_col, value="Excess Qty")
    cell.font = hdr_font; cell.fill = hdr_fill
    cell = ws2.cell(row=r, column=excess_col+1, value="W37-52 Inc")
    cell.font = hdr_font; cell.fill = hdr_fill
    r += 1

    inc_data = all_inc[sc]
    for stock_sku, excess_qty in sorted(STOCK.items(), key=lambda x: -x[1]):
        if stock_sku in DROPPED:
            continue
        model_sku = PROXY_MAP.get(stock_sku, stock_sku)
        discs = D[sc]["timeline"].get(model_sku, {}).get("opt_disc", [0]*52)

        label = stock_sku
        if stock_sku in PROXY_MAP:
            label = "{} (via {})".format(stock_sku, PROXY_MAP[stock_sku])

        ws2.cell(row=r, column=1, value=label).font = Font(name="Calibri", size=9, bold=True)
        ws2.cell(row=r, column=1).border = thin_border

        for ci, w in enumerate(w37_range):
            idx = w - 1  # 0-based
            d = discs[idx] if idx < len(discs) else 0
            cell = ws2.cell(row=r, column=ci+2, value=d if d > 0 else "")
            cell.font = Font(name="Calibri", size=8)
            cell.fill = disc_fill(d)
            cell.alignment = Alignment(horizontal="center")
            cell.border = thin_border

        ws2.cell(row=r, column=excess_col, value=excess_qty).font = body_font
        ws2.cell(row=r, column=excess_col, value=excess_qty).number_format = num_fmt
        w37_inc = inc_data.get(model_sku, {}).get("w37_inc", 0)
        ws2.cell(row=r, column=excess_col+1, value=w37_inc).font = body_font
        ws2.cell(row=r, column=excess_col+1).number_format = num_fmt
        r += 1
    r += 2

ws2.column_dimensions["A"].width = 22
for ci in range(len(w37_range)):
    ws2.column_dimensions[get_column_letter(ci+2)].width = 4.8
ws2.column_dimensions[get_column_letter(excess_col)].width = 12
ws2.column_dimensions[get_column_letter(excess_col+1)].width = 12

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SHEET 3: Charts
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ws3 = wb.create_sheet("Charts")
ws3.sheet_properties.tabColor = "8E44AD"

# Chart 1: Stock Clearance % by SKU (bar chart)
r = 1
ws3.cell(row=r, column=1, value="Stock Clearance % by SKU \u2014 W37-W52").font = title_font; r += 2

chart1_start = r
write_row(ws3, r, ["Stock SKU", "S1: Full Clear", "S2: Moderate", "S3: Constrained", "Excess Qty"], font=hdr_font, fill=hdr_fill); r += 1

for stock_sku, excess_qty in sorted(STOCK.items(), key=lambda x: -x[1]):
    if stock_sku in DROPPED:
        continue
    model_sku = PROXY_MAP.get(stock_sku, stock_sku)
    vals = [stock_sku]
    for sc in ["S1", "S2", "S3"]:
        w37_inc = all_inc[sc].get(model_sku, {}).get("w37_inc", 0)
        pct = min(100, w37_inc / excess_qty * 100) if excess_qty > 0 else 0
        vals.append(round(pct))
    vals.append(excess_qty)
    write_row(ws3, r, vals, font=body_font, number_format=num_fmt); r += 1
chart1_end = r - 1

c1 = BarChart()
c1.type = "col"
c1.grouping = "clustered"
c1.title = "Stock Clearance % by SKU (W37-W52)"
c1.y_axis.title = "Clearance %"
c1.style = 10
c1.width = 36
c1.height = 16

cats = Reference(ws3, min_col=1, min_row=chart1_start+1, max_row=chart1_end)
for col_idx in range(2, 5):
    data_ref = Reference(ws3, min_col=col_idx, min_row=chart1_start, max_row=chart1_end)
    c1.add_data(data_ref, titles_from_data=True)
c1.set_categories(cats)
bar_colors = ["E74C3C", "F39C12", "2980B9"]
for idx, color in enumerate(bar_colors):
    c1.series[idx].graphicalProperties.solidFill = color

ws3.add_chart(c1, "A{}".format(chart1_end + 2))
r = chart1_end + 20

# Chart 2: Weekly Revenue W37-52
r += 2
ws3.cell(row=r, column=1, value="Weekly Revenue W37-W52 by Scenario (\u20ac)").font = title_font; r += 2

chart2_start = r
write_row(ws3, r, ["Week", "No-Promo Base", "S1: Full Clear", "S2: Moderate", "S3: Constrained"], font=hdr_font, fill=hdr_fill); r += 1

for w in w37_range:
    idx = w - 1
    base_v = D["S1"]["weekly_chart"]["base"][idx]
    vals = [w, base_v]
    for sc in ["S1", "S2", "S3"]:
        vals.append(D[sc]["weekly_chart"]["optimal"][idx])
    write_row(ws3, r, vals, font=body_font, number_format=eur_fmt); r += 1
chart2_end = r - 1

c2 = LineChart()
c2.title = "Weekly Revenue W37-W52"
c2.y_axis.title = "Revenue (\u20ac)"
c2.x_axis.title = "Week"
c2.style = 10
c2.width = 36
c2.height = 16

cats2 = Reference(ws3, min_col=1, min_row=chart2_start+1, max_row=chart2_end)
colors2 = ["999999", "E74C3C", "F39C12", "2980B9"]
for col_idx in range(2, 6):
    data_ref = Reference(ws3, min_col=col_idx, min_row=chart2_start, max_row=chart2_end)
    c2.add_data(data_ref, titles_from_data=True)
c2.set_categories(cats2)
for idx, color in enumerate(colors2):
    c2.series[idx].graphicalProperties.line.solidFill = color
    c2.series[idx].graphicalProperties.line.width = 22000 if idx > 0 else 15000
    if idx == 0:
        c2.series[idx].graphicalProperties.line.dashStyle = "dash"

ws3.add_chart(c2, "A{}".format(chart2_end + 2))
r = chart2_end + 20

# Chart 3: Excess qty vs incremental units bar chart
r += 2
ws3.cell(row=r, column=1, value="Excess Stock vs Incremental Sell-Out (S1) \u2014 Top 10 SKUs").font = title_font; r += 2

chart3_start = r
write_row(ws3, r, ["Stock SKU", "Excess Qty", "S1 W37-52 Incremental"], font=hdr_font, fill=hdr_fill); r += 1

for stock_sku, excess_qty in sorted(STOCK.items(), key=lambda x: -x[1]):
    if stock_sku in DROPPED:
        continue
    model_sku = PROXY_MAP.get(stock_sku, stock_sku)
    w37_inc = all_inc["S1"].get(model_sku, {}).get("w37_inc", 0)
    write_row(ws3, r, [stock_sku, excess_qty, w37_inc], font=body_font, number_format=num_fmt); r += 1
chart3_end = r - 1

c3 = BarChart()
c3.type = "col"
c3.grouping = "clustered"
c3.title = "Excess Stock vs S1 Incremental Sell-Out"
c3.y_axis.title = "Units"
c3.style = 10
c3.width = 36
c3.height = 16

cats3 = Reference(ws3, min_col=1, min_row=chart3_start+1, max_row=chart3_end)
for col_idx in [2, 3]:
    data_ref = Reference(ws3, min_col=col_idx, min_row=chart3_start, max_row=chart3_end)
    c3.add_data(data_ref, titles_from_data=True)
c3.set_categories(cats3)
c3.series[0].graphicalProperties.solidFill = "E74C3C"
c3.series[1].graphicalProperties.solidFill = "2980B9"

ws3.add_chart(c3, "A{}".format(chart3_end + 2))

ws3.column_dimensions["A"].width = 14
for c in ["B", "C", "D", "E"]:
    ws3.column_dimensions[c].width = 18

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SHEET 4: Margin Analysis (W37-52 only)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ws4 = wb.create_sheet("Margin Analysis")
ws4.sheet_properties.tabColor = "C0392B"

r = 1
ws4.cell(row=r, column=1, value="Margin Erosion Analysis \u2014 W37-W52 Per-SKU").font = title_font; r += 1
base_margin_pct = D["S1"]["compare"]["current"]["margin"]
ws4.cell(row=r, column=1, value="Base margin: {:.1f}% | Red <20% | Orange <30% | Yellow <40% | Green >=50%".format(base_margin_pct)).font = Font(name="Calibri", size=10, color="666666"); r += 2

for sc, sc_name in [("S1", SC_NAMES["S1"]), ("S2", SC_NAMES["S2"]), ("S3", SC_NAMES["S3"])]:
    ws4.cell(row=r, column=1, value=sc_name).font = sec_font; r += 1

    # Header
    ws4.cell(row=r, column=1, value="Stock SKU").font = hdr_font
    ws4.cell(row=r, column=1).fill = hdr_fill
    for ci, w in enumerate(w37_range):
        cell = ws4.cell(row=r, column=ci+2, value="W{}".format(w))
        cell.font = Font(name="Calibri", bold=True, color=WHITE, size=8)
        cell.fill = hdr_fill
        cell.alignment = Alignment(horizontal="center")
    sum_col = len(w37_range) + 2
    for label in ["Avg Margin", "Min Margin"]:
        cell = ws4.cell(row=r, column=sum_col, value=label)
        cell.font = Font(name="Calibri", bold=True, color=WHITE, size=9)
        cell.fill = hdr_fill
        sum_col += 1
    r += 1

    for stock_sku in sorted(STOCK.keys(), key=lambda x: -STOCK[x]):
        if stock_sku in DROPPED:
            continue
        model_sku = PROXY_MAP.get(stock_sku, stock_sku)
        discs = D[sc]["timeline"].get(model_sku, {}).get("opt_disc", [0]*52)

        ws4.cell(row=r, column=1, value=stock_sku).font = Font(name="Calibri", size=9, bold=True)
        ws4.cell(row=r, column=1).border = thin_border

        margins = []
        cogs_share = 1 - base_margin_pct / 100
        for ci, w in enumerate(w37_range):
            idx = w - 1
            d = discs[idx] if idx < len(discs) else 0
            if d == 0:
                m = base_margin_pct
            else:
                m = max(0, (1 - cogs_share / (1 - d / 100)) * 100)
            margins.append(m)
            cell = ws4.cell(row=r, column=ci+2, value=round(m, 1))
            cell.font = Font(name="Calibri", size=8)
            cell.fill = margin_fill(m)
            cell.alignment = Alignment(horizontal="center")
            cell.border = thin_border
            cell.number_format = "0.0"

        avg_m = sum(margins) / len(margins)
        min_m = min(margins)
        sum_col = len(w37_range) + 2
        ws4.cell(row=r, column=sum_col, value=round(avg_m, 1)).font = bold_font
        ws4.cell(row=r, column=sum_col).fill = margin_fill(avg_m)
        ws4.cell(row=r, column=sum_col).number_format = "0.0"
        ws4.cell(row=r, column=sum_col+1, value=round(min_m, 1)).font = bold_font
        ws4.cell(row=r, column=sum_col+1).fill = margin_fill(min_m)
        ws4.cell(row=r, column=sum_col+1).number_format = "0.0"
        r += 1

    # Scenario margin summary
    rec = D[sc]["compare"]["recommended"]
    r += 1
    ws4.cell(row=r, column=1, value="Scenario margin: {:.1f}%".format(rec["margin"])).font = bold_font
    ws4.cell(row=r, column=4, value="vs base: {:.1f}%".format(base_margin_pct)).font = body_font
    ws4.cell(row=r, column=7, value="Margin drop: {:.1f}pp".format(base_margin_pct - rec["margin"])).font = Font(name="Calibri", size=10, bold=True, color=ACCENT_RED)
    r += 2

ws4.column_dimensions["A"].width = 15
for ci in range(len(w37_range)):
    ws4.column_dimensions[get_column_letter(ci+2)].width = 4.8
sum_start = len(w37_range) + 2
ws4.column_dimensions[get_column_letter(sum_start)].width = 12
ws4.column_dimensions[get_column_letter(sum_start+1)].width = 12

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SHEET 5: Recommendation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ws5 = wb.create_sheet("Recommendation")
ws5.sheet_properties.tabColor = ACCENT_GREEN

r = 1
ws5.cell(row=r, column=1, value="Recommendation: S1 (Full Clearance) for Stock Depletion Priority").font = title_font; r += 2

ws5.cell(row=r, column=1, value="Why S1").font = sec_font; r += 1
reasons = [
    ("Stock clearance priority", "Given the regulatory deadline, S1 (50% max, unconstrained) is the right starting point \u2014 it clears 100% of excess stock in aggregate."),
    ("W37-52 is sufficient", "~26K incremental units vs ~11K excess \u2014 even with model uncertainty, there is a 2.4x safety margin on the portfolio."),
    ("Problem SKUs identified", "HX9911/84, HX9992/44, HX9917/90 need non-price intervention (bundling, outlet, B2B) \u2014 price alone will not clear these."),
    ("Margin cost is known", "30.7% margin vs 53.6% base \u2014 a 22.9pp drop. The team can decide if this is acceptable vs the cost of holding unsold stock."),
    ("Event build-up supported", "The calendar shows discounting starting W37 and deepening into BFCM (W47-49) \u2014 aligns with the request to build up before events."),
]
for title, detail in reasons:
    ws5.cell(row=r, column=1, value=title).font = bold_font
    ws5.cell(row=r, column=2, value=detail).font = body_font
    r += 1

r += 1
ws5.cell(row=r, column=1, value="If Margin Matters More Than Expected").font = sec_font; r += 1
ws5.cell(row=r, column=1, value="S2 (35% max) still clears the portfolio in aggregate and saves ~5pp of margin (35.1% vs 30.7%).").font = body_font; r += 1
ws5.cell(row=r, column=1, value="The trade-off: ~16K fewer incremental units, reducing the safety margin from 2.4x to 1.9x.").font = body_font; r += 2

ws5.cell(row=r, column=1, value="Next Steps").font = sec_font; r += 1
steps = [
    "1. Confirm which SKUs can be handled via non-price levers (HX9911/84, HX9992/44, HX9917/90).",
    "2. Validate that the W37 start is operationally feasible (listings, price changes, ad setup).",
    "3. Lock in the BFCM (W47-49) and Big Deal Days (W41-42) event participation with Amazon.",
    "4. Share this analysis with the team for alignment, then finalize the calendar from S1 or S2.",
    "5. Consider a mid-point check at W44 to see if clearance is on track or if depth needs adjustment.",
]
for step in steps:
    ws5.cell(row=r, column=1, value=step).font = body_font; r += 1

ws5.column_dimensions["A"].width = 30
ws5.column_dimensions["B"].width = 100

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Save
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
out_path = os.path.join(
    r"c:\Users\310223340\OneDrive - Philips\MarketingAnalytics\RGM\Promo Effectiveness\simulator",
    "DE_DiamondClean_StockDepletion_2026-09-10.xlsx"
)
wb.save(out_path)
print("Saved: {}".format(out_path))
print("Sheets: {}".format(wb.sheetnames))
