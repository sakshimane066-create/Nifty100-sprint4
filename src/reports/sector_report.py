"""Sector reports: header page with median KPIs and best / worst, then a table of every company in the sector (spec 8.3)."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, TableStyle

from src.reports import common as cm_
from src.reports.common import BODY, H1, H2, SMALL, UW, ReportData, clip, num

NM = "n/m"


def sector_frame(data: ReportData, sector: str) -> pd.DataFrame:
    """Latest-year KPIs for every company in a sector, ranked by quality score."""
    ids = data.sectors.loc[data.sectors["broad_sector"] == sector, "company_id"]
    df = data.ratios[(data.ratios["is_latest"] == 1) & data.ratios["company_id"].isin(ids)].merge(
        data.companies[["id", "company_name"]], left_on="company_id", right_on="id")
    return df.sort_values("composite_quality_score", ascending=False, na_position="last").reset_index(drop=True)


def filename(sector: str, stamp: str | None = None) -> str:
    """<SECTOR>_report_YYYYMMDD.pdf with filesystem-safe sector name."""
    return f"{re.sub(r'[^A-Za-z0-9]+', '_', sector).strip('_')}_report_{stamp or date.today():%Y%m%d}.pdf" if not isinstance(stamp, str) else \
        f"{re.sub(r'[^A-Za-z0-9]+', '_', sector).strip('_')}_report_{stamp}.pdf"


def build_story(data: ReportData, sector: str) -> list:
    """Flowables for one sector report."""
    df = sector_frame(data, sector)
    fin = sector == "Financials"
    med = lambda c: df[c].median()  # noqa: E731
    scored = df.dropna(subset=["composite_quality_score"])
    best, worst = (scored.iloc[0], scored.iloc[-1]) if len(scored) else (None, None)
    tiles = [("Companies", str(len(df))), ("Median ROE", num(med("return_on_equity_pct"), 1, "%")), ("Median net margin", num(med("net_profit_margin_pct"), 1, "%")),
             ("Median quality score", num(med("composite_quality_score"), 0)), ("Best in sector", best["company_id"] if best is not None else "-"),
             ("Weakest in sector", worst["company_id"] if worst is not None else "-"), ("Median revenue CAGR 5Y", num(med("revenue_cagr_5y"), 1, "%")),
             ("Median profit CAGR 5Y", num(med("pat_cagr_5y"), 1, "%"))]
    med_rows = [[lab, NM if (fin and c in ("roce_pct", "debt_to_equity", "operating_profit_margin_pct")) else num(df[c].median(), nd, suf),
                 NM if (fin and c in ("roce_pct", "debt_to_equity", "operating_profit_margin_pct")) else num(df[c].quantile(0.25), nd, suf),
                 NM if (fin and c in ("roce_pct", "debt_to_equity", "operating_profit_margin_pct")) else num(df[c].quantile(0.75), nd, suf)]
                for lab, c, nd, suf in [("ROE", "return_on_equity_pct", 1, "%"), ("ROCE", "roce_pct", 1, "%"), ("Net profit margin", "net_profit_margin_pct", 1, "%"),
                                        ("Operating margin", "operating_profit_margin_pct", 1, "%"), ("Debt / equity", "debt_to_equity", 2, "x"),
                                        ("Revenue CAGR 5Y", "revenue_cagr_5y", 1, "%"), ("Profit CAGR 5Y", "pat_cagr_5y", 1, "%"), ("Quality score", "composite_quality_score", 0, "")]]
    hl = {}
    if best is not None:
        hl[best["company_id"]], hl[worst["company_id"]] = "#2E7D32", "#C62828"
    chart_df = df.dropna(subset=["return_on_equity_pct"])
    page1 = [Paragraph(f"{clip(sector)} sector report", H1),
             Paragraph(f"{len(df)} Nifty 100 companies  |  latest fiscal year per company  |  generated {date.today():%d %b %Y}", SMALL), Spacer(1, 8), cm_.tile_table(tiles),
             Paragraph("Sector median KPIs", H2), cm_.data_table(["KPI", "Median", "25th percentile", "75th percentile"], med_rows, [6, 4, 4, 4])]
    if fin:
        page1.append(Paragraph("Banks, NBFCs and insurers: ROCE, operating margin and D/E are not meaningful for them and are shown as n/m; compare ROE, margin and growth.", SMALL))
    if len(chart_df):
        page1 += [Spacer(1, 6), cm_.img(cm_.chart_hbar(chart_df["company_id"].tolist(), chart_df["return_on_equity_pct"].round(1).tolist(), "ROE % by company (green = best quality score, red = weakest)",
                                                       highlight=hl, h=min(9.0, 2.5 + 0.38 * len(chart_df))), UW)]
    header = ["Ticker", "Company", "ROE %", "ROCE %", "Net margin %", "D/E", "Rev CAGR 5Y %", "Profit CAGR 5Y %", "Quality"]
    rows = []
    for r in df.itertuples():
        f = bool(r.is_financial)
        rows.append([r.company_id, clip(r.company_name, 38), num(r.return_on_equity_pct), NM if f else num(r.roce_pct), num(r.net_profit_margin_pct),
                     NM if f else num(r.debt_to_equity, 2), num(r.revenue_cagr_5y), num(r.pat_cagr_5y), num(r.composite_quality_score, 0)])
    t = cm_.data_table(header, rows, [2.2, 5.0, 1.5, 1.6, 1.9, 1.4, 2.1, 2.2, 1.5], font=7.2)
    style = []
    for i, r in enumerate(df.itertuples(), start=1):
        if best is not None and r.company_id == best["company_id"]:
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#DDEFDD")))
        if worst is not None and r.company_id == worst["company_id"]:
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F8D7D7")))
    t.setStyle(TableStyle(style))
    return [cm_.fit(page1), PageBreak(), Paragraph(f"{clip(sector)} - all companies", H1),
            Paragraph("Ranked by Composite Quality Score. Green row = best in sector, red row = weakest.", SMALL), Spacer(1, 4), t]


def make_sector_report(data: ReportData, sector: str, out_dir: Path, stamp: str | None = None) -> Path:
    """Write <SECTOR>_report_YYYYMMDD.pdf."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename(sector, stamp or date.today().strftime("%Y%m%d"))
    doc = SimpleDocTemplate(str(path), pagesize=cm_.A4, leftMargin=cm_.MARGIN, rightMargin=cm_.MARGIN, topMargin=cm_.MARGIN + 0.2 * cm, bottomMargin=cm_.MARGIN + 0.2 * cm,
                            title=f"{sector} sector report", author="N100 Financial Intelligence Platform")
    deco = cm_.page_decor(f"{sector} - Sector Report")
    doc.build(build_story(data, sector), onFirstPage=deco, onLaterPages=deco)
    return path
