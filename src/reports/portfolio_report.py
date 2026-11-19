"""Portfolio summary: one A4 page per company in a single PDF (spec 8.2)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from src.reports import common as cm_
from src.reports.common import BODY, DASH, H1, H2, SMALL, UW, ReportData, clip, num

NM = "n/m"


def company_page(data: ReportData, t: str) -> list:
    """One compact page: identity, 6 KPI tiles, 3-year trend arrows, mini chart, top pros / cons."""
    co, last = data.company(t), data.latest(t)
    sector, sub = data.sector_of(t)
    hist = data.ratios[data.ratios["company_id"] == t].sort_values("fy")
    fin = bool(last["is_financial"])
    kpis = [("ROE", num(last["return_on_equity_pct"], 1, "%")), ("ROCE", NM if fin else num(last["roce_pct"], 1, "%")), ("Net margin", num(last["net_profit_margin_pct"], 1, "%")),
            ("Debt / equity", NM if fin else num(last["debt_to_equity"], 2, "x")), ("Revenue CAGR 5Y", num(last["revenue_cagr_5y"], 1, "%")),
            ("Quality score", num(last["composite_quality_score"], 0))]
    trend_rows = []
    for label, col, nd, suf in [("Revenue (Rs Cr)", "sales_cr", 0, ""), ("Net profit (Rs Cr)", "net_profit_cr", 0, ""), ("ROE", "return_on_equity_pct", 1, "%")]:
        s = hist[col].dropna()
        ago = s.iloc[-4] if len(s) > 3 else None
        trend_rows.append([Paragraph(label, BODY), Paragraph(num(s.iloc[-1] if len(s) else None, nd, suf, comma=True), BODY), Paragraph(num(ago, nd, suf, comma=True), BODY), cm_.arrow(cm_.trend_direction(s))])
    tt = Table([[Paragraph("<b>Metric</b>", BODY), Paragraph("<b>Latest</b>", BODY), Paragraph("<b>3 years ago</b>", BODY), Paragraph("<b>3Y direction</b>", BODY)]] + trend_rows,
               colWidths=[UW * 0.34, UW * 0.22, UW * 0.22, UW * 0.22])
    tt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), cm_.LIGHT), ("LINEBELOW", (0, 0), (-1, -1), 0.25, cm_.GREY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    gen = data.pros_cons[data.pros_cons["company_id"] == t].sort_values("confidence_pct", ascending=False)
    pros, cons = gen[gen["type"] == "pro"].head(2), gen[gen["type"] == "con"].head(2)
    pc = Table([[Paragraph("<b>Strengths</b>", BODY), Paragraph("<b>Watch-points</b>", BODY)],
                [[Paragraph("+ " + clip(r.text, 150), BODY) for r in pros.itertuples()] or [Paragraph(DASH, BODY)], [Paragraph("- " + clip(r.text, 150), BODY) for r in cons.itertuples()] or [Paragraph(DASH, BODY)]]],
               colWidths=[UW / 2, UW / 2])
    pc.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.4, cm_.GREY), ("INNERGRID", (0, 0), (-1, -1), 0.3, cm_.GREY), ("BACKGROUND", (0, 0), (-1, 0), cm_.LIGHT)]))
    return [Paragraph(clip(co["company_name"], 90), H1), Paragraph(f"{clip(t)}  |  {clip(sector)} - {clip(sub)}  |  FY{int(last['fy'])}", SMALL), Spacer(1, 8), cm_.tile_table(kpis, cols=3),
            Paragraph("Three-year direction", H2), tt, Spacer(1, 8),
            cm_.img(cm_.chart_bars(hist, {"sales_cr": "Revenue", "net_profit_cr": "Net profit"}, "Revenue and net profit (Rs Cr)", h=6.2), UW), Paragraph("Rule-based pros and cons", H2), pc]


def make_portfolio_report(data: ReportData, out_dir: Path, stamp: str | None = None, tickers: list[str] | None = None) -> Path:
    """Write portfolio_summary_YYYYMMDD.pdf with one page per company (all companies unless `tickers` is given)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"portfolio_summary_{stamp or date.today().strftime('%Y%m%d')}.pdf"
    story = []
    for i, t in enumerate(tickers or data.tickers()):
        story += ([PageBreak()] if i else []) + [cm_.fit(company_page(data, t))]
    doc = SimpleDocTemplate(str(path), pagesize=cm_.A4, leftMargin=cm_.MARGIN, rightMargin=cm_.MARGIN, topMargin=cm_.MARGIN + 0.2 * cm, bottomMargin=cm_.MARGIN + 0.2 * cm,
                            title="Nifty 100 portfolio summary", author="N100 Financial Intelligence Platform")
    deco = cm_.page_decor("Portfolio Summary")
    doc.build(story, onFirstPage=deco, onLaterPages=deco)
    return path
