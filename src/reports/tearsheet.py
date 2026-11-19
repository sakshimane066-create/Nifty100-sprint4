"""Company tearsheet: exactly 2 A4 pages per company (spec 8.1)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from src.reports import common as cm_
from src.reports.common import BODY, DASH, H1, H2, SMALL, UW, ReportData, clip, num

NM = "n/m"   # not meaningful (financial companies)


def _notes(data: ReportData, t: str, hist: pd.DataFrame, last: pd.Series) -> list[str]:
    out = []
    if last["is_financial"]:
        out.append("Financial company: ROCE and D/E are not meaningful for banks, NBFCs and insurers (deposits / policyholder funds count as borrowings).")
    if data.bs[data.bs["company_id"] == t].empty:
        out.append("No balance sheet is available in the source data for this company; balance-sheet ratios are blank.")
    elif hist["bs_scale_suspect"].sum():
        out.append(f"Balance-sheet ratios are blank for {int(hist['bs_scale_suspect'].sum())} year(s): the source balance sheet is on a different scale than the P&L (rule DQ-17).")
    if len(hist) < 5:
        out.append(f"Only {len(hist)} years of history are available; long-window growth rates are not computed.")
    if isinstance(last["cagr_flags"], str) and last["cagr_flags"]:
        out.append("Growth flags: " + last["cagr_flags"].rstrip(";").replace(";", "; ") + " (CAGR undefined when the base year is zero or negative, or the company moved to a loss).")
    return out


def build_story(data: ReportData, t: str) -> list:
    """Flowables for one company: page 1 (KPIs, revenue / profit, ROE / ROCE) + page 2 (balance sheet, cash flow, intelligence, pros / cons)."""
    co = data.company(t)
    sector, sub = data.sector_of(t)
    hist = data.ratios[data.ratios["company_id"] == t].sort_values("fy")
    last = data.latest(t)
    fin = bool(last["is_financial"])
    q = last["composite_quality_score"]

    head = Table([[Paragraph(clip(co["company_name"], 90), H1), [Paragraph("Quality score", cm_.TILE_L), Paragraph(f"{num(q, 0)}<font size=8 color='#6B7280'> /100</font>", cm_.TILE_V)]]],
                 colWidths=[UW - 3.2 * cm, 3.2 * cm])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOX", (1, 0), (1, 0), 0.4, cm_.GREY), ("BACKGROUND", (1, 0), (1, 0), cm_.LIGHT)]))
    kpis = [("ROE", num(last["return_on_equity_pct"], 1, "%")), ("ROCE", NM if fin else num(last["roce_pct"], 1, "%")),
            ("Net profit margin", num(last["net_profit_margin_pct"], 1, "%")), ("Operating margin", NM if fin else num(last["operating_profit_margin_pct"], 1, "%")),
            ("Debt / equity", NM if fin else num(last["debt_to_equity"], 2, "x")), ("Revenue CAGR 5Y", num(last["revenue_cagr_5y"], 1, "%")),
            ("Profit CAGR 5Y", num(last["pat_cagr_5y"], 1, "%")), ("Free cash flow (Rs Cr)", num(last["free_cash_flow_cr"], 0, "", True))]
    page1 = [head, Paragraph(f"{clip(t)}  |  {clip(sector)}  -  {clip(sub)}  |  Latest fiscal year: FY{int(last['fy'])}  |  {len(hist)} years of data", SMALL), Spacer(1, 4),
             Paragraph(clip(co["about_company"], 480), BODY), Spacer(1, 6), cm_.tile_table(kpis)]
    notes = _notes(data, t, hist, last)
    if notes:
        page1 += [Spacer(1, 4), Paragraph("<b>Data notes:</b> " + " ".join(clip(n, 260) for n in notes), SMALL)]
    page1 += [Spacer(1, 6), cm_.img(cm_.chart_bars(hist, {"sales_cr": "Revenue", "net_profit_cr": "Net profit"}, "Revenue and net profit (Rs Cr)"), UW),
              cm_.img(cm_.chart_lines(hist, {"return_on_equity_pct": "ROE %"} if fin else {"return_on_equity_pct": "ROE %", "roce_pct": "ROCE %"},
                                      "Return on equity" + ("" if fin else " and capital employed") + " (%)"), UW)]

    bs = data.bs[data.bs["company_id"] == t].sort_values("fy").copy()
    bs["equity"] = bs["equity_capital"] + bs["reserves"]
    bs = bs[~bs["year"].str.endswith("-09")]  # drop the interim Sep-2024 balance sheet
    cf = data.cf[data.cf["company_id"] == t].sort_values("fy")
    cfi = data.cfi[data.cfi["company_id"] == t]
    cfi = cfi.iloc[0] if len(cfi) else None
    bs_chart = cm_.chart_bars(bs, {"equity": "Equity + reserves", "borrowings": "Borrowings", "other_liabilities": "Other liabilities"}, "Liabilities composition (Rs Cr)", w=8.6, h=6.6, stacked=True) if not bs.empty and not (hist["bs_scale_suspect"].sum() > 3) else None
    cf_chart = cm_.chart_bars(cf, {"operating_activity": "Operating", "investing_activity": "Investing", "financing_activity": "Financing"}, "Cash flow (Rs Cr)", w=8.6, h=6.6)
    charts = Table([[cm_.img(bs_chart, UW / 2 - 6), cm_.img(cf_chart, UW / 2 - 6)]], colWidths=[UW / 2, UW / 2])
    charts.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))

    page2 = [Paragraph("Balance sheet, cash flow and quality", H1), Spacer(1, 2), charts, Paragraph("Cash flow intelligence", H2)]
    if cfi is not None:
        rows = [["Earnings quality (CFO / PAT, 5Y)", f"{cfi['cfo_quality']}  ({num(cfi['cfo_pat_5y'], 2, 'x')})", "CapEx intensity (5Y avg)", f"{cfi['capex_category']}  ({num(cfi['capex_intensity_5y_pct'], 1, '%')})"],
                ["FCF conversion (5Y)", f"{cfi['fcf_conversion_tier']}  ({num(cfi['fcf_conversion_5y_pct'], 0, '%')})", "FCF CAGR 5Y / 10Y", f"{num(cfi['fcf_cagr_5y'], 1, '%')}  /  {num(cfi['fcf_cagr_10y'], 1, '%')}"],
                ["Capital allocation (latest)", cfi["capital_allocation"], "Deleveraging years (last 5)", f"{int(cfi['deleveraging_years_5y'])}"],
                ["Distress signal (latest year)", "YES - CFO < 0 funded by financing" if cfi["distress_latest"] else "No", "Cash flow caveat", "CapEx proxy = |investing CF|"]]
        t2 = cm_.data_table(["Metric", "Result", "Metric", "Result"], rows, [4.6, 4.4, 4.2, 4.4], font=7.6, align_right_from=9)
        page2.append(t2)
    page2.append(Paragraph("Growth", H2))
    g = [["Revenue CAGR", num(last["revenue_cagr_3y"], 1, "%"), num(last["revenue_cagr_5y"], 1, "%"), num(last["revenue_cagr_10y"], 1, "%")],
         ["Net profit CAGR", num(last["pat_cagr_3y"], 1, "%"), num(last["pat_cagr_5y"], 1, "%"), num(last["pat_cagr_10y"], 1, "%")],
         ["EPS CAGR", DASH, num(last["eps_cagr_5y"], 1, "%"), DASH]]
    page2.append(cm_.data_table(["Metric", "3 years", "5 years", "10 years"], g, [5, 4, 4, 4]))
    gen = data.pros_cons[data.pros_cons["company_id"] == t].sort_values("confidence_pct", ascending=False)
    pros, cons = gen[gen["type"] == "pro"].head(4), gen[gen["type"] == "con"].head(4)

    def col(df: pd.DataFrame, sym: str) -> list:
        return [Paragraph(f"{sym} {clip(r.text, 180)} <font color='#6B7280'>({r.confidence_pct:.0f}%)</font>", BODY) for r in df.itertuples()] or [Paragraph("-", BODY)]

    pc = Table([[Paragraph("<b>Strengths</b>", BODY), Paragraph("<b>Watch-points</b>", BODY)], [col(pros, "+"), col(cons, "-")]], colWidths=[UW / 2, UW / 2])
    pc.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (0, 0), (0, 0), colors_light("#E8F5E9")), ("BACKGROUND", (1, 0), (1, 0), colors_light("#FDECEA")),
                            ("BOX", (0, 0), (-1, -1), 0.4, cm_.GREY), ("INNERGRID", (0, 0), (-1, -1), 0.3, cm_.GREY), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    page2 += [Paragraph("Pros and cons (rule-based)", H2), pc, Spacer(1, 5),
              Paragraph("Rules are KPI thresholds applied to this company's financial history; the percentage is rule confidence. They are screening aids, not investment advice. "
                        "Source: Screener.in / BSE filings supplied by Bluestock; all figures in Rs Crore unless stated.", SMALL)]
    return [cm_.fit(page1), PageBreak(), cm_.fit(page2)]


def colors_light(hex_: str):
    from reportlab.lib import colors

    return colors.HexColor(hex_)


def make_tearsheet(data: ReportData, t: str, out_dir: Path) -> Path:
    """Write <TICKER>_tearsheet.pdf and return its path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{t.replace('&', '_').replace('/', '_')}_tearsheet.pdf"
    name = data.company(t)["company_name"]
    doc = SimpleDocTemplate(str(path), pagesize=cm_.A4, leftMargin=cm_.MARGIN, rightMargin=cm_.MARGIN, topMargin=cm_.MARGIN + 0.2 * cm, bottomMargin=cm_.MARGIN + 0.2 * cm,
                            title=f"{name} - Tearsheet", author="N100 Financial Intelligence Platform", subject=f"{t} company tearsheet")
    deco = cm_.page_decor(f"{t} - Company Tearsheet")
    doc.build(build_story(data, t), onFirstPage=deco, onLaterPages=deco)
    return path
