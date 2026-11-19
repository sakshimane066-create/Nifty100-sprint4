"""Shared data loading, charts and ReportLab building blocks for all PDF reports."""
from __future__ import annotations

import io
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from reportlab.graphics.charts.barcharts import HorizontalBarChart, VerticalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.shapes import Drawing, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, KeepInFrame, Paragraph, Table, TableStyle

try:  # matplotlib gives the nicest PNG charts, but it is optional: some Windows policies block its DLLs
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    HAVE_MPL = True
except Exception:  # ImportError, blocked DLL, ...
    plt = None
    HAVE_MPL = False

ROOT = Path(__file__).resolve().parents[2]
NAVY, TEAL, GREY, LIGHT = colors.HexColor("#1F3864"), colors.HexColor("#2E86AB"), colors.HexColor("#6B7280"), colors.HexColor("#F3F4F6")
GREEN, RED, AMBER = colors.HexColor("#2E7D32"), colors.HexColor("#C62828"), colors.HexColor("#B26A00")
MARGIN = 1.6 * cm
PAGE_W, PAGE_H = A4
UW = PAGE_W - 2 * MARGIN            # usable width; every table's column widths sum to this
FRAME_H = PAGE_H - 2 * MARGIN - 1.0 * cm
MAX_CELL = 200                      # cells longer than this are truncated with an ellipsis (risk R-08)
DASH = "-"
FOOTER = "N100 Financial Intelligence Platform  |  CONFIDENTIAL - internal use only  |  Figures in Rs Crore unless stated  |  Market data omitted (simulated)"

_ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=_ss["Heading1"], fontName="Helvetica-Bold", fontSize=18, leading=21, textColor=NAVY, spaceAfter=2)
H2 = ParagraphStyle("H2", parent=_ss["Heading2"], fontName="Helvetica-Bold", fontSize=11.5, leading=14, textColor=NAVY, spaceBefore=6, spaceAfter=3)
BODY = ParagraphStyle("Body", parent=_ss["BodyText"], fontName="Helvetica", fontSize=8.6, leading=11.2)
SMALL = ParagraphStyle("Small", parent=BODY, fontSize=7.4, leading=9.4, textColor=GREY)
CELL = ParagraphStyle("Cell", parent=BODY, fontSize=8, leading=10, wordWrap="CJK")
TILE_L = ParagraphStyle("TileL", parent=SMALL, fontSize=7.2, alignment=1)
TILE_V = ParagraphStyle("TileV", parent=BODY, fontName="Helvetica-Bold", fontSize=15, leading=18, alignment=1, textColor=NAVY)


def clip(text: object, n: int = MAX_CELL) -> str:
    """Escape and truncate text for a Paragraph cell."""
    s = "" if text is None or (isinstance(text, float) and pd.isna(text)) else str(text)
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return s if len(s) <= n else s[: n - 3].rstrip() + "..."


def num(v: object, nd: int = 1, suffix: str = "", comma: bool = False) -> str:
    """Format a number; '-' for missing."""
    if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v):
        return DASH
    return f"{v:,.{nd}f}{suffix}" if comma else f"{v:.{nd}f}{suffix}"


@dataclass
class ReportData:
    """All tables the reports need, loaded once."""
    companies: pd.DataFrame
    sectors: pd.DataFrame
    ratios: pd.DataFrame
    pl: pd.DataFrame
    bs: pd.DataFrame
    cf: pd.DataFrame
    pros_cons: pd.DataFrame
    cfi: pd.DataFrame

    @classmethod
    def load(cls, db_path: Path = ROOT / "data" / "nifty100.db") -> "ReportData":
        with sqlite3.connect(db_path) as c:
            q = lambda s: pd.read_sql(s, c)  # noqa: E731
            return cls(q("SELECT * FROM companies"), q("SELECT * FROM sectors"), q("SELECT * FROM financial_ratios ORDER BY company_id, fy"),
                       q("SELECT * FROM profitandloss ORDER BY company_id, fy"), q("SELECT * FROM balancesheet ORDER BY company_id, fy"),
                       q("SELECT * FROM cashflow ORDER BY company_id, fy"), q("SELECT * FROM pros_cons_generated"), q("SELECT * FROM cashflow_intelligence"))

    def tickers(self) -> list[str]:
        return sorted(self.companies["id"])

    def company(self, t: str) -> pd.Series:
        return self.companies[self.companies["id"] == t].iloc[0]

    def sector_of(self, t: str) -> tuple[str, str]:
        r = self.sectors[self.sectors["company_id"] == t].iloc[0]
        return r["broad_sector"], r["sub_sector"]

    def latest(self, t: str) -> pd.Series:
        r = self.ratios[(self.ratios["company_id"] == t) & (self.ratios["is_latest"] == 1)]
        return r.iloc[0]


# ------------------------------------------------------------------ charts
def _png(fig) -> io.BytesIO:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _style(ax, title: str) -> None:
    ax.set_title(title, fontsize=9, fontweight="bold", color="#1F3864", loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=7)
    ax.grid(axis="y", alpha=0.25)


def chart_bars(df: pd.DataFrame, cols: dict[str, str], title: str, w: float = 17.4, h: float = 7.0, stacked: bool = False) -> io.BytesIO | None:
    """Bar chart of columns over fiscal year; None if there is nothing to draw."""
    d = df.dropna(subset=list(cols), how="all").tail(11)
    if d.empty:
        return None
    if not HAVE_MPL:
        return native_bars(d, cols, title, w, h, stacked)
    fig, ax = plt.subplots(figsize=(w / 2.54, h / 2.54))
    x = range(len(d))
    palette = ["#2E86AB", "#1F3864", "#F4A261", "#8AB17D"]
    if stacked:
        bottom = pd.Series(0.0, index=d.index)
        for i, (c, label) in enumerate(cols.items()):
            ax.bar(list(x), d[c].fillna(0), bottom=bottom, label=label, color=palette[i % 4], width=0.65)
            bottom += d[c].fillna(0)
    else:
        n = len(cols)
        for i, (c, label) in enumerate(cols.items()):
            ax.bar([k + (i - (n - 1) / 2) * 0.8 / n for k in x], d[c].fillna(0), width=0.8 / n, label=label, color=palette[i % 4])
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"'{int(v) % 100:02d}" for v in d["fy"]], rotation=0)
    ax.axhline(0, color="#888", lw=0.6)
    ax.legend(fontsize=7, frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.14))
    _style(ax, title)
    return _png(fig)


def chart_lines(df: pd.DataFrame, cols: dict[str, str], title: str, w: float = 17.4, h: float = 6.0) -> io.BytesIO | None:
    """Line chart of ratio columns over fiscal year; None if all values are missing."""
    d = df.tail(11)
    if d[list(cols)].isna().all().all():
        return None
    if not HAVE_MPL:
        return native_lines(d, cols, title, w, h)
    fig, ax = plt.subplots(figsize=(w / 2.54, h / 2.54))
    for i, (c, label) in enumerate(cols.items()):
        ax.plot(d["fy"], d[c], marker="o", ms=3, lw=1.6, label=label, color=["#1F3864", "#2E86AB", "#F4A261"][i % 3])
    ax.legend(fontsize=7, frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.14))
    ax.set_xticks(list(d["fy"]))
    ax.set_xticklabels([f"'{int(v) % 100:02d}" for v in d["fy"]])
    _style(ax, title)
    return _png(fig)


def chart_hbar(labels: list[str], values: list[float], title: str, highlight: dict[str, str] | None = None, w: float = 17.4, h: float = 6.0):
    """Horizontal bar chart (sector reports)."""
    if not HAVE_MPL:
        return native_hbar(labels, values, title, highlight, w, h)
    fig, ax = plt.subplots(figsize=(w / 2.54, h / 2.54))
    cols = [(highlight or {}).get(lbl, "#2E86AB") for lbl in labels]
    ax.barh(labels[::-1], values[::-1], color=cols[::-1])
    ax.tick_params(axis="y", labelsize=6)
    _style(ax, title)
    ax.grid(axis="x", alpha=0.25)
    ax.grid(axis="y", visible=False)
    return _png(fig)


# ------------------------------------------------------------------ native (ReportLab vector) charts: used when matplotlib is unavailable
_PAL = [colors.HexColor("#2E86AB"), colors.HexColor("#1F3864"), colors.HexColor("#F4A261"), colors.HexColor("#8AB17D")]


def _native_frame(w_cm: float, h_cm: float, title: str, labels: list[str]) -> tuple[Drawing, float, float]:
    w, h = w_cm * 28.35, h_cm * 28.35
    d = Drawing(w, h)
    d.add(String(0, h - 10, title, fontName="Helvetica-Bold", fontSize=9, fillColor=NAVY))
    x = 0.0
    for i, lab in enumerate(labels):
        d.add(Rect(x, 2, 7, 7, fillColor=_PAL[i % 4], strokeColor=_PAL[i % 4]))
        d.add(String(x + 10, 3, lab, fontName="Helvetica", fontSize=7, fillColor=GREY))
        x += 22 + 4.2 * len(lab)
    return d, w, h


def _num_axis(ax, lo: float, hi: float) -> None:
    ax.valueMin, ax.valueMax = lo, hi
    ax.labels.fontName, ax.labels.fontSize = "Helvetica", 6.5
    ax.labelTextFormat = lambda v: f"{v:,.0f}" if abs(hi - lo) >= 10 else f"{v:,.1f}"
    ax.strokeColor = colors.HexColor("#CCCCCC")
    ax.visibleGrid, ax.gridStrokeColor = True, colors.HexColor("#E5E7EB")


def _span(vals: list[float], stacked: bool = False, rows: list[list[float]] | None = None) -> tuple[float, float]:
    lo, hi = min(0.0, min(vals)), max(0.0, max(vals))
    if stacked and rows:
        hi = max(hi, max(sum(c) for c in zip(*rows)))
    pad = (hi - lo) * 0.06 or 1.0
    return lo - (pad if lo < 0 else 0), hi + pad


def native_bars(d_: pd.DataFrame, cols: dict[str, str], title: str, w: float, h: float, stacked: bool) -> Drawing:
    """Grouped or stacked bar chart drawn with ReportLab shapes."""
    d_ = d_.dropna(subset=list(cols), how="all").tail(11)
    d, W, H = _native_frame(w, h, title, list(cols.values()))
    rows = [[float(v) if pd.notna(v) else 0.0 for v in d_[c]] for c in cols]
    ch = VerticalBarChart()
    ch.x, ch.y, ch.width, ch.height = 44, 20, W - 54, H - 44
    ch.data = rows
    ch.categoryAxis.categoryNames = [f"'{int(v) % 100:02d}" for v in d_["fy"]]
    ch.categoryAxis.labels.fontName, ch.categoryAxis.labels.fontSize = "Helvetica", 6.5
    ch.categoryAxis.labelAxisMode = "low"
    if stacked:
        ch.categoryAxis.style = "stacked"
    lo, hi = _span([v for r in rows for v in r], stacked, rows)
    _num_axis(ch.valueAxis, lo, hi)
    for i in range(len(rows)):
        ch.bars[i].fillColor, ch.bars[i].strokeColor = _PAL[i % 4], None
    ch.barSpacing, ch.groupSpacing = 0.5, 6
    d.add(ch)
    return d


def native_lines(d_: pd.DataFrame, cols: dict[str, str], title: str, w: float, h: float) -> Drawing:
    """Line chart (categorical x) drawn with ReportLab shapes."""
    d_ = d_.tail(11)
    d, W, H = _native_frame(w, h, title, list(cols.values()))
    rows = [[float(v) if pd.notna(v) else None for v in d_[c]] for c in cols]
    flat = [v for r in rows for v in r if v is not None]
    ch = HorizontalLineChart()
    ch.x, ch.y, ch.width, ch.height = 44, 20, W - 54, H - 44
    ch.data = rows
    ch.categoryAxis.categoryNames = [f"'{int(v) % 100:02d}" for v in d_["fy"]]
    ch.categoryAxis.labels.fontName, ch.categoryAxis.labels.fontSize = "Helvetica", 6.5
    lo, hi = _span(flat)
    _num_axis(ch.valueAxis, min(lo, min(flat)), hi)
    for i in range(len(rows)):
        ch.lines[i].strokeColor, ch.lines[i].strokeWidth = _PAL[i % 4], 1.6
        ch.lines[i].symbol = None
    d.add(ch)
    return d


def native_hbar(labels: list[str], values: list[float], title: str, highlight: dict[str, str] | None, w: float, h: float) -> Drawing:
    """Horizontal bar chart (first label on top)."""
    d, W, H = _native_frame(w, h, title, [])
    ch = HorizontalBarChart()
    ch.x, ch.y, ch.width, ch.height = 52, 8, W - 62, H - 30
    ch.data = [list(values[::-1])]
    ch.categoryAxis.categoryNames = labels[::-1]
    ch.categoryAxis.labels.fontName, ch.categoryAxis.labels.fontSize = "Helvetica", 6
    lo, hi = _span(list(values))
    _num_axis(ch.valueAxis, lo, hi)
    ch.bars.strokeColor = None
    for i, lab in enumerate(labels[::-1]):
        ch.bars[(0, i)].fillColor = colors.HexColor((highlight or {}).get(lab, "#2E86AB"))
    ch.barSpacing = 1.5
    d.add(ch)
    return d


def img(buf, width: float, ratio_hint: float = 0.32):
    """Embed a chart PNG at a given width (aspect preserved); a note if the chart could not be drawn."""
    if buf is None:
        return Paragraph("Chart unavailable - no data in the source for this company.", SMALL)
    if isinstance(buf, Drawing):  # native vector chart: scale to the requested width
        k = width / buf.width
        buf.scale(k, k)
        buf.width, buf.height = buf.width * k, buf.height * k
        return buf
    from reportlab.lib.utils import ImageReader

    w, h = ImageReader(buf).getSize()
    buf.seek(0)
    return Image(buf, width=width, height=width * h / w)


# ------------------------------------------------------------------ building blocks
def tile_table(items: list[tuple[str, str]], cols: int = 4) -> Table:
    """Grid of KPI tiles (label over value); column widths sum to UW."""
    cells = [[Paragraph(clip(v), TILE_V), Paragraph(clip(k), TILE_L)] for k, v in items]
    rows = []
    for i in range(0, len(cells), cols):
        chunk = cells[i:i + cols] + [[Paragraph("", TILE_V), Paragraph("", TILE_L)]] * (cols - len(cells[i:i + cols]))
        rows.append([Table([[c[0]], [c[1]]], colWidths=[UW / cols - 6], style=[("BOTTOMPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 4)]) for c in chunk])
    t = Table(rows, colWidths=[UW / cols] * cols)
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")), ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
                           ("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    return t


def data_table(header: list[str], rows: list[list[str]], widths: list[float], font: float = 7.6, zebra: bool = True, align_right_from: int = 2) -> Table:
    """Table with wrapped Paragraph cells; widths are scaled so they always sum to UW."""
    scale = UW / sum(widths)
    cs = ParagraphStyle("c", parent=CELL, fontSize=font, leading=font + 2)
    hs = ParagraphStyle("h", parent=cs, fontName="Helvetica-Bold", textColor=colors.white)
    data = [[Paragraph(clip(h), hs) for h in header]] + [[Paragraph(clip(c), cs) for c in r] for r in rows]
    t = Table(data, colWidths=[w * scale for w in widths], repeatRows=1)
    st = [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
          ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB"))]
    if zebra:
        st += [("BACKGROUND", (0, i), (-1, i), LIGHT) for i in range(2, len(data), 2)]
    t.setStyle(TableStyle(st))
    return t


def arrow(direction: str, size: float = 12) -> Drawing:
    """Trend arrow drawn as a shape (font glyphs for arrows are not in the built-in fonts)."""
    d = Drawing(size, size)
    if direction == "up":
        d.add(Polygon([size / 2, size, 0, 0, size, 0], fillColor=GREEN, strokeColor=GREEN))
    elif direction == "down":
        d.add(Polygon([size / 2, 0, 0, size, size, size], fillColor=RED, strokeColor=RED))
    else:
        d.add(Rect(0, size * 0.35, size, size * 0.3, fillColor=GREY, strokeColor=GREY))
    return d


def trend_direction(series: pd.Series, years: int = 3, tol: float = 0.05) -> str:
    """'up' / 'down' / 'flat' from the change over the last `years` annual points (relative change beyond +-tol)."""
    s = series.dropna()
    if len(s) <= years:
        return "flat"
    a, b = s.iloc[-1 - years], s.iloc[-1]
    if a == 0:
        return "flat"
    ch = (b - a) / abs(a)
    return "up" if ch > tol else "down" if ch < -tol else "flat"


def fit(flowables: list, height: float = FRAME_H) -> KeepInFrame:
    """Shrink a page's content to fit the frame, so a page can never overflow onto the next."""
    return KeepInFrame(UW, height, flowables, mode="shrink")


def page_decor(title: str):
    """onPage callback: thin header rule, footer text and page number."""
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(NAVY)
        canvas.setLineWidth(1.2)
        canvas.line(MARGIN, PAGE_H - MARGIN + 6, PAGE_W - MARGIN, PAGE_H - MARGIN + 6)
        canvas.setFont("Helvetica-Bold", 7.5)
        canvas.setFillColor(NAVY)
        canvas.drawString(MARGIN, PAGE_H - MARGIN + 10, "N100 FINANCIAL INTELLIGENCE")
        canvas.setFont("Helvetica", 7.5)
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - MARGIN + 10, title[:90])
        canvas.setFillColor(GREY)
        canvas.setFont("Helvetica", 6.3)
        canvas.drawString(MARGIN, MARGIN - 18, FOOTER)
        canvas.drawRightString(PAGE_W - MARGIN, MARGIN - 18, f"Page {doc.page}")
        canvas.restoreState()
    return draw
