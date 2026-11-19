from pathlib import Path

import pandas as pd
import pytest
from pypdf import PdfReader

from src.reports import common as c
from src.reports.portfolio_report import make_portfolio_report
from src.reports.sector_report import filename, make_sector_report
from src.reports.tearsheet import make_tearsheet

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def data(conn):
    return c.ReportData.load()


def text_of(path: Path) -> str:
    return "\n".join(p.extract_text() for p in PdfReader(path).pages)


@pytest.mark.parametrize("ticker", ["TCS", "SBIN", "HDFCBANK", "BEL", "M&M"])
def test_tearsheet_is_exactly_two_pages_and_substantial(data, tmp_path, ticker):
    p = make_tearsheet(data, ticker, tmp_path)
    assert len(PdfReader(p).pages) == 2 and p.stat().st_size >= (50 if c.HAVE_MPL else 8) * 1024  # vector fallback charts are smaller
    assert p.name.endswith("_tearsheet.pdf")


def test_tearsheet_content_and_edge_case_notes(data, tmp_path):
    t = text_of(make_tearsheet(data, "SBIN", tmp_path))
    assert "State Bank of India" in t and "No balance sheet" in t and "n/m" in t  # edge case handled, financial ROCE/D-E not shown
    t2 = text_of(make_tearsheet(data, "BEL", tmp_path))
    assert "DQ-17" in t2  # scale-suspect balance sheet is disclosed


def test_tearsheet_never_prints_simulated_valuation(data, tmp_path):
    assert "P/E" not in text_of(make_tearsheet(data, "TCS", tmp_path))


def test_sector_report_has_summary_and_all_companies(data, tmp_path):
    p = make_sector_report(data, "Real Estate", tmp_path, stamp="20260101")
    assert p.name == "Real_Estate_report_20260101.pdf" and len(PdfReader(p).pages) == 2
    t = text_of(p)
    assert "Sector median KPIs" in t and "DLF" in t and "LODHA" in t


def test_financials_report_marks_not_meaningful_kpis(data, tmp_path):
    assert "n/m" in text_of(make_sector_report(data, "Financials", tmp_path))


def test_portfolio_one_page_per_company(data, tmp_path):
    p = make_portfolio_report(data, tmp_path, stamp="20260101", tickers=["TCS", "INFY", "SBIN"])
    assert len(PdfReader(p).pages) == 3 and "Tata Consultancy" in text_of(p)


def test_filename_format():
    assert filename("Consumer Staples", "20260101") == "Consumer_Staples_report_20260101.pdf"


def test_helpers():
    assert c.clip("a" * 300).endswith("...") and len(c.clip("a" * 300)) == c.MAX_CELL
    assert c.clip("A & B <x>") == "A &amp; B &lt;x&gt;" and c.clip(None) == ""
    assert c.num(None) == "-" and c.num(1234.5, 0, "", True) == "1,234" or c.num(1234.5, 0, "", True) == "1,235"
    s = pd.Series([100, 105, 110, 90, 120.0])
    assert c.trend_direction(s) == "up" and c.trend_direction(pd.Series([100, 100, 100, 70.0])) == "down" and c.trend_direction(pd.Series([1.0, 2.0])) == "flat"


def test_table_widths_sum_to_usable_width():
    t = c.data_table(["a", "b", "c"], [["1", "2", "3"]], [1, 2, 3])
    assert abs(sum(t._colWidths) - c.UW) < 0.01


# ---- acceptance AC-17, only checked when the reports have been generated (make reports)
def test_ac17_all_tearsheets_exist_and_large_enough():
    d = ROOT / "reports" / "tearsheets"
    files = list(d.glob("*_tearsheet.pdf"))
    if len(files) < 92:
        pytest.skip("run `make reports` first")
    assert len(files) == 92
    if c.HAVE_MPL:  # the 50 KB gate assumes PNG charts; reports built with the vector fallback are ~10 KB
        assert all(f.stat().st_size >= 50 * 1024 for f in files)


# ---- matplotlib is optional (some Windows Application Control policies block its DLLs): everything must work without it
def test_reports_work_without_matplotlib(data, tmp_path, monkeypatch):
    monkeypatch.setattr(c, "HAVE_MPL", False)
    for t in ("TCS", "SBIN"):
        p = make_tearsheet(data, t, tmp_path)
        assert len(PdfReader(p).pages) == 2 and "Revenue" in text_of(p)
    assert len(PdfReader(make_sector_report(data, "Financials", tmp_path)).pages) >= 2
    assert len(PdfReader(make_portfolio_report(data, tmp_path, tickers=["TCS", "BEL"])).pages) == 2


def test_non_report_modules_import_without_matplotlib():
    import subprocess
    import sys

    code = ("import sys; sys.modules['matplotlib'] = None; sys.modules['matplotlib.pyplot'] = None; "
            "import src.dashboard.utils.tables, src.analytics.cashflow_intel, src.analytics.valuation, src.analytics.ratios, "
            "src.analytics.peer, src.nlp.run, src.screener.engine, src.etl.loader; print('ok')")
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr[-500:]
