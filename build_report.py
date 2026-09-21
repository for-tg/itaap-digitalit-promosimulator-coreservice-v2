"""Build the Diamond Clean Scenario Analysis Excel report."""
import json, os
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import LineChart, BarChart, Reference
from openpyxl.chart.series import SeriesLabel
from openpyxl.chart.label import DataLabelList

# ── Load data ──────────────────────────────────────────────
files = {"A": "scenario_A.json", "B": "scenario_B.json", "C": "scenario_C.json"}
D = {}
for k, fn in files.items():
    with open(fn, encoding="utf-8") as f:
        D[k] = json.load(f)

SKUS = list(D["A"]["timeline"].keys())
WEEKS = list(range(1, 53))

# ── Styles ─────────────────────────────────────────────────
PHILIPS_BLUE  = "003366"
PHILIPS_LIGHT = "D6E4F0"
ACCENT_GREEN  = "27AE60"
ACCENT_ORANGE = "E67E22"
ACCENT_RED    = "C0392B"
LIGHT_GRAY    = "F2F2F2"
MED_GRAY      = "D9D9D9"
WHITE         = "FFFFFF"

hdr_font   = Font(name="Calibri", bold=True, color=WHITE, size=11)
hdr_fill   = PatternFill("solid", fgColor=PHILIPS_BLUE)
sub_font   = Font(name="Calibri", bold=True, size=11)
sub_fill   = PatternFill("solid", fgColor=PHILIPS_LIGHT)
title_font = Font(name="Calibri", bold=True, size=14, color=PHILIPS_BLUE)
sec_font   = Font(name="Calibri", bold=True, size=12, color=PHILIPS_BLUE)
body_font  = Font(name="Calibri", size=10)
bold_font  = Font(name="Calibri", bold=True, size=10)
eur_fmt    = "#,##0"
num_fmt    = "#,##0"
thin_border = Border(
    left=Side(style="thin", color=MED_GRAY),
    right=Side(style="thin", color=MED_GRAY),
    top=Side(style="thin", color=MED_GRAY),
    bottom=Side(style="thin", color=MED_GRAY),
)

def write_row(ws, row, data, start_col=1, font=None, fill=None, number_format=None, alignment=None):
    for i, val in enumerate(data):
        cell = ws.cell(row=row, column=start_col+i, value=val)
        if font: cell.font = font
        if fill: cell.fill = fill
        if alignment: cell.alignment = alignment
        if number_format and isinstance(val, (int, float)): cell.number_format = number_format
        cell.border = thin_border

def disc_fill(d):
    if d == 0 or d is None: return PatternFill("solid", fgColor=WHITE)
    if d <= 10: return PatternFill("solid", fgColor="E8F5E9")
    if d <= 20: return PatternFill("solid", fgColor="FFF9C4")
    if d <= 30: return PatternFill("solid", fgColor="FFE0B2")
    return PatternFill("solid", fgColor="FFCDD2")

wb = Workbook()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SHEET 1: Executive Summary
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ws = wb.active
ws.title = "Executive Summary"
ws.sheet_properties.tabColor = PHILIPS_BLUE

r = 1
ws.cell(row=r, column=1, value="Diamond Clean Stock Depletion \u2014 Promo Scenario Analysis").font = title_font
r += 1
ws.cell(row=r, column=1, value="Germany Amazon RTB \u00b7 10 Diamond Clean SKUs \u00b7 2026 Forward Plan").font = Font(name="Calibri", size=11, color="666666")
r += 1
ws.cell(row=r, column=1, value="Generated: 2026-09-10 \u00b7 Model: M7 CausalForestDML \u00b7 Economics: Triple Net").font = Font(name="Calibri", size=10, color="999999")
r += 2

# Context block
ws.cell(row=r, column=1, value="Context & Objective").font = sec_font; r += 1
context_lines = [
    "Regulatory requirement to deplete Diamond Clean stock by end of 2026.",
    "Stakeholder concern: Prime Day 2026 was over-discounted \u2014 need smarter depth allocation.",
    "Goal: Find the right promo intensity to accelerate stock depletion while protecting margin.",
    "Three scenarios tested to show the trade-off space: aggressive, event-focused, and margin-protected.",
]
for line in context_lines:
    ws.cell(row=r, column=1, value="\u2022  " + line).font = body_font; r += 1
r += 1

# Scenario descriptions
ws.cell(row=r, column=1, value="Scenario Definitions").font = sec_font; r += 1
sc_descs = [
    ("A: Aggressive Depletion", "Turnover obj. | Max 40% disc. | Unconstrained budget | Equal quarterly split",
     "Maximum volume at any margin cost"),
    ("B: Event-Focused (Recommended)", "Turnover obj. | Max 25% disc. | Budget = 1x hist. | Q-split mirrors 2025 actual (12/13/21/54)",
     "Concentrate spend on BFCM/events using proven seasonal shape, preserve margin off-peak"),
    ("C: Margin-Protected", "Profit obj. | Max 25% disc. | Unconstrained budget | Equal quarterly split",
     "Only promote where profitable"),
]
headers = ["Scenario", "Parameters", "Rationale"]
write_row(ws, r, headers, font=hdr_font, fill=hdr_fill)
r += 1
for name, params, rationale in sc_descs:
    write_row(ws, r, [name, params, rationale], font=body_font)
    r += 1
r += 1

# Comparison table
ws.cell(row=r, column=1, value="Portfolio Comparison").font = sec_font; r += 1
base = D["A"]["compare"]["current"]
hist = D["A"]["compare"]["historical"]

comp_headers = ["Metric", "No-Promo Baseline", "Historical 2025", "A: Aggressive", "B: Event-Focused", "C: Margin-Prot."]
write_row(ws, r, comp_headers, font=hdr_font, fill=hdr_fill)
r += 1

metrics = [
    ("Revenue (\u20ac)", "turnover", eur_fmt),
    ("Profit (\u20ac)", "profit", eur_fmt),
    ("Margin (%)", "margin", '0.0"%"'),
    ("Volume (units)", "qty", num_fmt),
    ("Promo Weeks", "promo_weeks", num_fmt),
    ("Promo Spend (\u20ac)", "promo_spend", eur_fmt),
]
for label, key, nf in metrics:
    bv = base.get(key, 0)
    hv = hist.get(key, 0)
    vals = [D[sc]["compare"]["recommended"].get(key, 0) for sc in ["A","B","C"]]
    row_data = [label, bv, hv] + vals
    write_row(ws, r, row_data, font=body_font, number_format=nf)
    ws.cell(row=r, column=1).font = bold_font
    r += 1

r += 1

# Incremental metrics
ws.cell(row=r, column=1, value="Incremental Impact vs No-Promo Baseline").font = sec_font; r += 1
inc_headers = ["Metric", "A: Aggressive", "B: Event-Focused", "C: Margin-Prot."]
write_row(ws, r, inc_headers, font=hdr_font, fill=hdr_fill)
r += 1
bq = base["qty"]; br = base["turnover"]; bp = base["profit"]

inc_rows = []
for label, key, nf in [
    ("Incremental Units", "qty", num_fmt),
    ("Incremental Revenue (\u20ac)", "turnover", eur_fmt),
    ("Profit Impact (\u20ac)", "profit", eur_fmt),
]:
    base_val = base[key]
    vals = [D[sc]["compare"]["recommended"][key] - base_val for sc in ["A","B","C"]]
    inc_rows.append((label, vals, nf))

# Revenue ROI
spend_vals = [D[sc]["compare"]["recommended"]["promo_spend"] for sc in ["A","B","C"]]
rev_inc = [D[sc]["compare"]["recommended"]["turnover"] - br for sc in ["A","B","C"]]
roi_vals = [rv/sp if sp > 0 else 0 for rv, sp in zip(rev_inc, spend_vals)]
inc_rows.append(("Revenue ROI", roi_vals, '0.00"x"'))

for label, vals, nf in inc_rows:
    write_row(ws, r, [label]+vals, font=body_font, number_format=nf)
    ws.cell(row=r, column=1).font = bold_font
    r += 1

r += 2

# Key Takeaways
ws.cell(row=r, column=1, value="Key Takeaways").font = sec_font; r += 1
takeaways = [
    "1. Scenario A clears +95K incremental units but destroys margin (50% to 25%) and costs 7.7M in promo spend. Revenue ROI is only 0.36x.",
    "2. Scenario B (recommended) delivers +39K units and +1.3M revenue at 40% margin \u2014 half the volume of A but at 2.6x less spend.",
    "3. Scenario C shows near-zero profitable promo opportunity at 25% max \u2014 validating that these Premium SKUs need volume-driven discounting.",
    "4. At BFCM (W47-48), all scenarios go deep \u2014 the model confirms this is the highest-ROI event window.",
    "5. Prime Day (W28-29) shows lower optimal depth in B (5-25%) vs A (40%) \u2014 supporting the over-discounting concern.",
    "6. Recommendation: Lead with Scenario B for stock depletion planning. Use A only if regulatory deadline forces maximum urgency.",
]
for t in takeaways:
    ws.cell(row=r, column=1, value=t).font = body_font; r += 1

ws.column_dimensions["A"].width = 42
for col in ["B","C","D","E","F"]:
    ws.column_dimensions[col].width = 22

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SHEET 2: SKU Deep Dive
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ws2 = wb.create_sheet("SKU Deep Dive")
ws2.sheet_properties.tabColor = "1B7A43"

r = 1
ws2.cell(row=r, column=1, value="Per-SKU Profit, Spend & ROI \u2014 All Scenarios").font = title_font; r += 2

for sc, sc_name in [("A","Scenario A: Aggressive Depletion"),("B","Scenario B: Event-Focused"),("C","Scenario C: Margin-Protected")]:
    ws2.cell(row=r, column=1, value=sc_name).font = sec_font; r += 1
    headers = ["SKU", "Base Profit (\u20ac)", "Optimal Profit (\u20ac)", "Gain (\u20ac)", "Promo Spend (\u20ac)", "Promo ROI", "Promo Weeks", "Avg Depth (%)", "Confidence"]
    write_row(ws2, r, headers, font=hdr_font, fill=hdr_fill)
    r += 1

    st = D[sc]["deep_dive"]["sku_table"]
    total_gain = 0; total_spend = 0; total_wks = 0
    for row_data in st:
        sku = row_data["sku"]
        discs = D[sc]["timeline"][sku]["opt_disc"]
        on_weeks = [d for d in discs if d > 0]
        nw = len(on_weeks)
        avg_d = sum(on_weeks)/len(on_weeks)/100 if on_weeks else 0
        total_gain += row_data["gain"]
        total_spend += row_data["promo_spend"]
        total_wks += nw
        vals = [sku, row_data["base_profit"], row_data["opt_profit"], row_data["gain"],
                row_data["promo_spend"], row_data["roi"] or 0, nw, avg_d, row_data["confidence"]]
        write_row(ws2, r, vals, font=body_font, number_format=eur_fmt)
        ws2.cell(row=r, column=6).number_format = "0.00"
        ws2.cell(row=r, column=8).number_format = "0%"
        r += 1
    # Total row
    total_roi = total_gain/total_spend if total_spend > 0 else 0
    write_row(ws2, r, ["TOTAL", "", "", total_gain, total_spend, total_roi, total_wks, "", ""],
              font=bold_font, fill=PatternFill("solid", fgColor=LIGHT_GRAY), number_format=eur_fmt)
    ws2.cell(row=r, column=6).number_format = "0.00"
    r += 2

ws2.column_dimensions["A"].width = 14
for c in ["B","C","D","E"]:
    ws2.column_dimensions[c].width = 18
ws2.column_dimensions["F"].width = 12
ws2.column_dimensions["G"].width = 14
ws2.column_dimensions["H"].width = 14
ws2.column_dimensions["I"].width = 20

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SHEET 3: Calendar
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ws3 = wb.create_sheet("Promo Calendar")
ws3.sheet_properties.tabColor = "E67E22"

r = 1
ws3.cell(row=r, column=1, value="52-Week Promo Calendar \u2014 Discount Depth (%)").font = title_font; r += 1
ws3.cell(row=r, column=1, value="White = no promo | Green \u226410% | Yellow \u226420% | Orange \u226430% | Red >30%").font = Font(name="Calibri", size=10, color="666666"); r += 2

event_weeks = {28: "PD", 29: "PD", 41: "BDD", 42: "BDD", 47: "BF", 48: "BF", 49: "BF"}

for sc, sc_name in [("A","Scenario A: Aggressive (Turnover, 40% max, unconstrained)"),
                     ("B","Scenario B: Event-Focused (Turnover, 25% max, budget-capped, Q4-heavy)"),
                     ("C","Scenario C: Margin-Protected (Profit, 25% max, unconstrained)")]:
    ws3.cell(row=r, column=1, value=sc_name).font = sec_font; r += 1

    # Event marker row
    ws3.cell(row=r, column=1, value="Events").font = Font(name="Calibri", size=9, color="999999", italic=True)
    for w in WEEKS:
        cell = ws3.cell(row=r, column=w+1, value=event_weeks.get(w, ""))
        cell.font = Font(name="Calibri", size=8, color=ACCENT_ORANGE, bold=True)
        cell.alignment = Alignment(horizontal="center")
    r += 1

    # Header row
    ws3.cell(row=r, column=1, value="SKU").font = hdr_font
    ws3.cell(row=r, column=1).fill = hdr_fill
    for w in WEEKS:
        cell = ws3.cell(row=r, column=w+1, value="W{}".format(w))
        cell.font = Font(name="Calibri", bold=True, color=WHITE, size=8)
        cell.fill = hdr_fill
        cell.alignment = Alignment(horizontal="center")
    r += 1

    for sku in SKUS:
        discs = D[sc]["timeline"][sku]["opt_disc"]
        ws3.cell(row=r, column=1, value=sku).font = Font(name="Calibri", size=9, bold=True)
        ws3.cell(row=r, column=1).border = thin_border
        for i, w in enumerate(WEEKS):
            d = discs[i] if i < len(discs) else 0
            cell = ws3.cell(row=r, column=w+1, value=d if d > 0 else "")
            cell.font = Font(name="Calibri", size=8)
            cell.fill = disc_fill(d)
            cell.alignment = Alignment(horizontal="center")
            cell.border = thin_border
        r += 1
    r += 2

ws3.column_dimensions["A"].width = 13
for w in WEEKS:
    ws3.column_dimensions[get_column_letter(w+1)].width = 4.5

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SHEET 4: Event Deep Dive
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ws4 = wb.create_sheet("Event Deep Dive")
ws4.sheet_properties.tabColor = "C0392B"

r = 1
ws4.cell(row=r, column=1, value="Event-Week Discount Depth Comparison").font = title_font; r += 1
ws4.cell(row=r, column=1, value="How each scenario treats the three key Amazon DE events").font = Font(name="Calibri", size=11, color="666666"); r += 2

events = [
    ("Prime Day (W28-29)", [27, 28]),
    ("Big Deal Days (W41-42)", [40, 41]),
    ("Black Friday / Cyber Monday (W47-48-49)", [46, 47, 48]),
]

for ev_name, wk_indices in events:
    ws4.cell(row=r, column=1, value=ev_name).font = sec_font; r += 1

    # Header
    headers = ["SKU"]
    for sc_name in ["A: Aggressive", "B: Event-Focused", "C: Margin-Prot."]:
        for wi in wk_indices:
            headers.append("{}:W{}".format(sc_name[0], wi+1))
        headers.append("")
    write_row(ws4, r, headers, font=hdr_font, fill=hdr_fill)
    r += 1

    for sku in SKUS:
        vals = [sku]
        for sc in ["A", "B", "C"]:
            discs = D[sc]["timeline"][sku]["opt_disc"]
            for wi in wk_indices:
                d = discs[wi] if wi < len(discs) else 0
                vals.append(d if d > 0 else "\u2014")
            vals.append("")
        write_row(ws4, r, vals, font=body_font)
        col = 2
        for sc in ["A", "B", "C"]:
            discs_sc = D[sc]["timeline"][sku]["opt_disc"]
            for wi in wk_indices:
                d = discs_sc[wi] if wi < len(discs_sc) else 0
                ws4.cell(row=r, column=col).fill = disc_fill(d)
                ws4.cell(row=r, column=col).alignment = Alignment(horizontal="center")
                col += 1
            col += 1
        r += 1
    r += 2

ws4.column_dimensions["A"].width = 14
for c in range(2, 20):
    ws4.column_dimensions[get_column_letter(c)].width = 12

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SHEET 5: Recommendation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ws5 = wb.create_sheet("Recommendation")
ws5.sheet_properties.tabColor = ACCENT_GREEN

r = 1
ws5.cell(row=r, column=1, value="Recommendation: Scenario B \u2014 Event-Focused Strategy").font = title_font; r += 2

ws5.cell(row=r, column=1, value="Why Scenario B").font = sec_font; r += 1
reasons = [
    ("Volume delivery", "+39K incremental units (35% above baseline) \u2014 meaningful stock depletion without the margin destruction of Scenario A."),
    ("Margin preservation", "39.8% margin vs 24.6% in Scenario A \u2014 saves 1.7M in absolute profit while still driving significant volume."),
    ("Better ROI", "0.46x revenue ROI vs 0.36x in Scenario A \u2014 every euro of promo spend works harder."),
    ("Event discipline", "Deep discounts (25-45%) concentrated at BFCM where traffic is highest; lighter (5-25%) at Prime Day."),
    ("Budget efficiency", "2.9M spend vs 7.7M in Scenario A \u2014 achieves 41% of A's incremental units at 38% of the cost."),
]
for title, detail in reasons:
    ws5.cell(row=r, column=1, value=title).font = bold_font
    ws5.cell(row=r, column=2, value=detail).font = body_font
    r += 1

r += 1
ws5.cell(row=r, column=1, value="What Scenario C Tells Us").font = sec_font; r += 1
ws5.cell(row=r, column=1, value="The profit-optimized scenario barely promotes \u2014 only 32 promo-weeks across 10 SKUs, generating +862 incremental units.").font = body_font; r += 1
ws5.cell(row=r, column=1, value="This confirms that Diamond Clean stock depletion requires accepting margin trade-off. The question is how much, not whether.").font = body_font; r += 2

ws5.cell(row=r, column=1, value="Next Steps").font = sec_font; r += 1
next_steps = [
    "1. Validate excess stock quantities per SKU to translate unit uplift into stock runway weeks.",
    "2. Refine Scenario B with actual stock-by-SKU constraints \u2014 some SKUs may need deeper/lighter treatment.",
    "3. Consider a Scenario B+ variant with 30% max discount (between B at 25% and A at 40%) if B alone does not clear enough.",
    "4. Align on Q4 event calendar (exact Prime Day / Big Deal Days / BFCM dates) for week-level precision.",
    "5. Model can be improved further with more data \u2014 this is a directional first pass for immediate planning.",
]
for step in next_steps:
    ws5.cell(row=r, column=1, value=step).font = body_font; r += 1

ws5.column_dimensions["A"].width = 24
ws5.column_dimensions["B"].width = 100

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SHEET 6: Charts (data tables + embedded charts)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ws6 = wb.create_sheet("Charts")
ws6.sheet_properties.tabColor = "8E44AD"

# ── Chart 1: Weekly Revenue by Scenario ──
r = 1
ws6.cell(row=r, column=1, value="Weekly Revenue Comparison by Scenario (€)").font = title_font; r += 2

# Data table for the chart
chart1_start = r
headers = ["Week", "No-Promo Baseline", "A: Aggressive", "B: Event-Focused", "C: Margin-Protected"]
write_row(ws6, r, headers, font=hdr_font, fill=hdr_fill)
r += 1

for i, w in enumerate(WEEKS):
    base_v = D["A"]["weekly_chart"]["base"][i]
    vals = [w, base_v]
    for sc in ["A", "B", "C"]:
        vals.append(D[sc]["weekly_chart"]["optimal"][i])
    write_row(ws6, r, vals, font=body_font, number_format=eur_fmt)
    r += 1
chart1_end = r - 1

# Build the chart
c1 = LineChart()
c1.title = "Weekly Revenue: Scenario Comparison"
c1.y_axis.title = "Revenue (€)"
c1.x_axis.title = "Week"
c1.style = 10
c1.width = 36
c1.height = 16

cats = Reference(ws6, min_col=1, min_row=chart1_start+1, max_row=chart1_end)
colors = ["999999", "E74C3C", "2980B9", "27AE60"]
labels = ["No-Promo Baseline", "A: Aggressive", "B: Event-Focused", "C: Margin-Protected"]
for col_idx in range(2, 6):
    data_ref = Reference(ws6, min_col=col_idx, min_row=chart1_start, max_row=chart1_end)
    c1.add_data(data_ref, titles_from_data=True)
c1.set_categories(cats)
for idx, color in enumerate(colors):
    c1.series[idx].graphicalProperties.line.solidFill = color
    c1.series[idx].graphicalProperties.line.width = 22000 if idx > 0 else 15000
    if idx == 0:
        c1.series[idx].graphicalProperties.line.dashStyle = "dash"

ws6.add_chart(c1, "A{}".format(chart1_end + 2))
r = chart1_end + 20

# ── Chart 2: Weekly Volume (units) by Scenario ──
r += 2
ws6.cell(row=r, column=1, value="Weekly Volume Comparison by Scenario (units)").font = title_font; r += 2

# We need to compute weekly volume. The weekly_chart only has revenue.
# Approximate: weekly volume = weekly revenue / avg price per unit
# Or better: use the base qty and scaling from volume_factor
# Actually the compare section has total qty. We can scale weekly revenue by (qty/revenue) ratio
# to get weekly qty. This is approximate but directionally correct.

chart2_start = r
headers = ["Week", "No-Promo Baseline", "A: Aggressive", "B: Event-Focused", "C: Margin-Protected"]
write_row(ws6, r, headers, font=hdr_font, fill=hdr_fill)
r += 1

# Compute price-per-unit ratios for scaling
base_ppu = D["A"]["compare"]["current"]["turnover"] / D["A"]["compare"]["current"]["qty"]
sc_ppus = {}
for sc in ["A", "B", "C"]:
    rec = D[sc]["compare"]["recommended"]
    sc_ppus[sc] = rec["turnover"] / rec["qty"] if rec["qty"] > 0 else base_ppu

for i, w in enumerate(WEEKS):
    base_rev_w = D["A"]["weekly_chart"]["base"][i]
    base_qty_w = round(base_rev_w / base_ppu)
    vals = [w, base_qty_w]
    for sc in ["A", "B", "C"]:
        opt_rev_w = D[sc]["weekly_chart"]["optimal"][i]
        vals.append(round(opt_rev_w / sc_ppus[sc]))
    write_row(ws6, r, vals, font=body_font, number_format=num_fmt)
    r += 1
chart2_end = r - 1

c2 = LineChart()
c2.title = "Weekly Volume: Scenario Comparison"
c2.y_axis.title = "Units"
c2.x_axis.title = "Week"
c2.style = 10
c2.width = 36
c2.height = 16

cats2 = Reference(ws6, min_col=1, min_row=chart2_start+1, max_row=chart2_end)
for col_idx in range(2, 6):
    data_ref = Reference(ws6, min_col=col_idx, min_row=chart2_start, max_row=chart2_end)
    c2.add_data(data_ref, titles_from_data=True)
c2.set_categories(cats2)
for idx, color in enumerate(colors):
    c2.series[idx].graphicalProperties.line.solidFill = color
    c2.series[idx].graphicalProperties.line.width = 22000 if idx > 0 else 15000
    if idx == 0:
        c2.series[idx].graphicalProperties.line.dashStyle = "dash"

ws6.add_chart(c2, "A{}".format(chart2_end + 2))
r = chart2_end + 20

# ── Chart 3: Cumulative Promo Spend ──
r += 2
ws6.cell(row=r, column=1, value="Cumulative Promo Spend by Scenario (€)").font = title_font; r += 2

chart3_start = r
headers = ["Week", "A: Aggressive", "B: Event-Focused", "C: Margin-Protected"]
write_row(ws6, r, headers, font=hdr_font, fill=hdr_fill)
r += 1

# Compute weekly spend from the revenue difference (optimal - base)
# promo_spend_week ~= (optimal_rev - base_rev) * (total_spend / total_rev_uplift)
cum_spends = {"A": [], "B": [], "C": []}
for sc in ["A", "B", "C"]:
    total_rev_uplift = sum(D[sc]["weekly_chart"]["optimal"]) - sum(D[sc]["weekly_chart"]["base"])
    total_spend = D[sc]["compare"]["recommended"]["promo_spend"]
    ratio = total_spend / total_rev_uplift if total_rev_uplift > 0 else 0
    cum = 0
    for i in range(52):
        weekly_uplift = D[sc]["weekly_chart"]["optimal"][i] - D[sc]["weekly_chart"]["base"][i]
        weekly_spend = max(0, weekly_uplift * ratio)
        cum += weekly_spend
        cum_spends[sc].append(round(cum))

for i, w in enumerate(WEEKS):
    vals = [w, cum_spends["A"][i], cum_spends["B"][i], cum_spends["C"][i]]
    write_row(ws6, r, vals, font=body_font, number_format=eur_fmt)
    r += 1
chart3_end = r - 1

c3 = LineChart()
c3.title = "Cumulative Promo Spend"
c3.y_axis.title = "Cumulative Spend (€)"
c3.x_axis.title = "Week"
c3.style = 10
c3.width = 36
c3.height = 16

cats3 = Reference(ws6, min_col=1, min_row=chart3_start+1, max_row=chart3_end)
spend_colors = ["E74C3C", "2980B9", "27AE60"]
for col_idx in range(2, 5):
    data_ref = Reference(ws6, min_col=col_idx, min_row=chart3_start, max_row=chart3_end)
    c3.add_data(data_ref, titles_from_data=True)
c3.set_categories(cats3)
for idx, color in enumerate(spend_colors):
    c3.series[idx].graphicalProperties.line.solidFill = color
    c3.series[idx].graphicalProperties.line.width = 22000

ws6.add_chart(c3, "A{}".format(chart3_end + 2))
r = chart3_end + 20

# ── Chart 4: Per-SKU Profit Gain Comparison (bar chart) ──
r += 2
ws6.cell(row=r, column=1, value="Per-SKU Profit Gain by Scenario (€)").font = title_font; r += 2

chart4_start = r
headers = ["SKU", "A: Aggressive", "B: Event-Focused", "C: Margin-Protected"]
write_row(ws6, r, headers, font=hdr_font, fill=hdr_fill)
r += 1

for sku in SKUS:
    vals = [sku]
    for sc in ["A", "B", "C"]:
        st = D[sc]["deep_dive"]["sku_table"]
        row_match = [s for s in st if s["sku"] == sku][0]
        vals.append(row_match["gain"])
    write_row(ws6, r, vals, font=body_font, number_format=eur_fmt)
    r += 1
chart4_end = r - 1

c4 = BarChart()
c4.type = "col"
c4.grouping = "clustered"
c4.title = "Profit Gain by SKU and Scenario"
c4.y_axis.title = "Profit Gain (€)"
c4.style = 10
c4.width = 36
c4.height = 16

cats4 = Reference(ws6, min_col=1, min_row=chart4_start+1, max_row=chart4_end)
for col_idx in range(2, 5):
    data_ref = Reference(ws6, min_col=col_idx, min_row=chart4_start, max_row=chart4_end)
    c4.add_data(data_ref, titles_from_data=True)
c4.set_categories(cats4)
bar_colors = ["E74C3C", "2980B9", "27AE60"]
for idx, color in enumerate(bar_colors):
    c4.series[idx].graphicalProperties.solidFill = color

ws6.add_chart(c4, "A{}".format(chart4_end + 2))

ws6.column_dimensions["A"].width = 14
for c in ["B", "C", "D", "E"]:
    ws6.column_dimensions[c].width = 20

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SHEET 7: Margin Erosion Analysis
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ws7 = wb.create_sheet("Margin Analysis")
ws7.sheet_properties.tabColor = "C0392B"

r = 1
ws7.cell(row=r, column=1, value="Margin Erosion Analysis — Per-SKU Per-Week").font = title_font; r += 1
ws7.cell(row=r, column=1, value="Estimated effective margin % after discount, by week. Base margin: {:.1f}%".format(
    D["A"]["compare"]["current"]["margin"])).font = Font(name="Calibri", size=10, color="666666"); r += 1
ws7.cell(row=r, column=1, value="Effective margin = Base margin × (1 - discount_depth / (1 - COGS_share)). Red < 25% | Orange < 35% | Yellow < 45% | Green >= 45%").font = Font(name="Calibri", size=9, color="999999"); r += 2

base_margin_pct = D["A"]["compare"]["current"]["margin"]  # 50.2

def margin_fill(m):
    if m is None: return PatternFill("solid", fgColor=WHITE)
    if m < 25: return PatternFill("solid", fgColor="FFCDD2")
    if m < 35: return PatternFill("solid", fgColor="FFE0B2")
    if m < 45: return PatternFill("solid", fgColor="FFF9C4")
    return PatternFill("solid", fgColor="E8F5E9")

for sc, sc_name in [("A","Scenario A: Aggressive Depletion"),
                     ("B","Scenario B: Event-Focused (Recommended)"),
                     ("C","Scenario C: Margin-Protected")]:
    ws7.cell(row=r, column=1, value=sc_name).font = sec_font; r += 1

    # Header
    ws7.cell(row=r, column=1, value="SKU").font = hdr_font
    ws7.cell(row=r, column=1).fill = hdr_fill
    for w in WEEKS:
        cell = ws7.cell(row=r, column=w+1, value="W{}".format(w))
        cell.font = Font(name="Calibri", bold=True, color=WHITE, size=8)
        cell.fill = hdr_fill
        cell.alignment = Alignment(horizontal="center")
    # Add summary columns
    sum_col = 54
    for label in ["Avg Margin", "Min Margin", "Wks < 30%"]:
        cell = ws7.cell(row=r, column=sum_col, value=label)
        cell.font = Font(name="Calibri", bold=True, color=WHITE, size=9)
        cell.fill = hdr_fill
        cell.alignment = Alignment(horizontal="center")
        sum_col += 1
    r += 1

    for sku in SKUS:
        discs = D[sc]["timeline"][sku]["opt_disc"]
        ws7.cell(row=r, column=1, value=sku).font = Font(name="Calibri", size=9, bold=True)
        ws7.cell(row=r, column=1).border = thin_border

        margins = []
        for i, w in enumerate(WEEKS):
            d = discs[i] if i < len(discs) else 0
            if d == 0:
                m = base_margin_pct
            else:
                # Effective margin after discount:
                # At discount d%, selling price drops by d%. COGS is fixed.
                # margin = 1 - COGS / (base_price * (1 - d/100))
                # = 1 - (1 - base_margin) / (1 - d/100)
                cogs_share = 1 - base_margin_pct / 100
                m = max(0, (1 - cogs_share / (1 - d / 100)) * 100)
            margins.append(m)
            cell = ws7.cell(row=r, column=w+1, value=round(m, 1))
            cell.font = Font(name="Calibri", size=8)
            cell.fill = margin_fill(m)
            cell.alignment = Alignment(horizontal="center")
            cell.border = thin_border
            cell.number_format = '0.0'

        # Summary columns
        promo_margins = [m for m in margins]
        avg_m = sum(promo_margins) / len(promo_margins)
        min_m = min(promo_margins)
        wks_below_30 = sum(1 for m in promo_margins if m < 30)

        ws7.cell(row=r, column=54, value=round(avg_m, 1)).font = bold_font
        ws7.cell(row=r, column=54).number_format = '0.0'
        ws7.cell(row=r, column=54).fill = margin_fill(avg_m)
        ws7.cell(row=r, column=55, value=round(min_m, 1)).font = bold_font
        ws7.cell(row=r, column=55).number_format = '0.0'
        ws7.cell(row=r, column=55).fill = margin_fill(min_m)
        ws7.cell(row=r, column=56, value=wks_below_30).font = bold_font
        ws7.cell(row=r, column=56).fill = PatternFill("solid", fgColor="FFCDD2") if wks_below_30 > 10 else PatternFill("solid", fgColor=WHITE)
        r += 1

    # Portfolio average row
    ws7.cell(row=r, column=1, value="PORTFOLIO AVG").font = Font(name="Calibri", size=9, bold=True, color=PHILIPS_BLUE)
    ws7.cell(row=r, column=1).fill = PatternFill("solid", fgColor=LIGHT_GRAY)
    for w_idx, w in enumerate(WEEKS):
        week_margins = []
        for sku in SKUS:
            d = D[sc]["timeline"][sku]["opt_disc"][w_idx] if w_idx < len(D[sc]["timeline"][sku]["opt_disc"]) else 0
            if d == 0:
                m = base_margin_pct
            else:
                cogs_share = 1 - base_margin_pct / 100
                m = max(0, (1 - cogs_share / (1 - d / 100)) * 100)
            week_margins.append(m)
        avg = sum(week_margins) / len(week_margins)
        cell = ws7.cell(row=r, column=w+1, value=round(avg, 1))
        cell.font = Font(name="Calibri", size=8, bold=True)
        cell.fill = margin_fill(avg)
        cell.alignment = Alignment(horizontal="center")
        cell.number_format = '0.0'
    r += 2

    # Margin summary for this scenario
    rec = D[sc]["compare"]["recommended"]
    ws7.cell(row=r, column=1, value="Scenario margin: {:.1f}%".format(rec["margin"])).font = bold_font
    ws7.cell(row=r, column=3, value="vs base: {:.1f}%".format(base_margin_pct)).font = body_font
    ws7.cell(row=r, column=5, value="Margin drop: {:.1f}pp".format(base_margin_pct - rec["margin"])).font = Font(name="Calibri", size=10, bold=True, color=ACCENT_RED)
    r += 2

ws7.column_dimensions["A"].width = 15
for w in WEEKS:
    ws7.column_dimensions[get_column_letter(w+1)].width = 4.8
for c in [54, 55, 56]:
    ws7.column_dimensions[get_column_letter(c)].width = 12

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Save
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
out_path = os.path.join(
    r"c:\Users\310223340\OneDrive - Philips\MarketingAnalytics\RGM\Promo Effectiveness\simulator",
    "DE_DiamondClean_Scenario_Analysis_2026-09-10.xlsx"
)
wb.save(out_path)
print("Saved: {}".format(out_path))
print("Sheets: {}".format(wb.sheetnames))
