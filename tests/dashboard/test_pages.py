"""Every dashboard page must render without exception, including edge-case tickers."""
import glob
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[2]
PAGES = sorted(glob.glob(str(ROOT / "src/dashboard/pages/*.py"))) + [str(ROOT / "src/dashboard/app.py")]


@pytest.fixture(autouse=True)
def _need_db(conn):
    pass


@pytest.mark.parametrize("page", PAGES, ids=[Path(p).name for p in PAGES])
def test_page_renders(page):
    at = AppTest.from_file(page, default_timeout=90).run()
    assert not at.exception


@pytest.mark.parametrize("ticker", ["TCS", "SBIN", "JIOFIN", "HDFCBANK", "M&M"])
@pytest.mark.parametrize("page", ["02_profile.py", "05_trends.py", "08_reports.py"])
def test_company_pages_edge_tickers(page, ticker):
    at = AppTest.from_file(str(ROOT / "src/dashboard/pages" / page), default_timeout=90)
    at.session_state["ticker"] = ticker
    at.run()
    assert not at.exception



def _screener():
    return AppTest.from_file(str(ROOT / "src/dashboard/pages/03_screener.py"), default_timeout=90).run()


def test_screener_preset_buttons_fill_sliders():
    at = _screener()
    btn = next(b for b in at.sidebar.button if b.key == "btn_Quality")
    btn.click().run()
    assert not at.exception
    assert at.session_state["s_roe"] == 15.0 and at.session_state["s_de"] == 1.0 and at.session_state["s_rev"] == 10.0
    assert "companies match your filters" in at.subheader[0].value and int(at.subheader[0].value.split()[0]) >= 10


def test_screener_all_six_presets_run():
    at = _screener()
    for label in ["Quality", "Value", "Growth", "Dividend", "Debt-Free", "Turnaround"]:
        next(b for b in at.sidebar.button if b.key == f"btn_{label}").click().run()
        assert not at.exception, label


def test_screener_extreme_slider_values_do_not_crash():
    at = _screener()
    for lo_or_hi in (0, 1):  # all sliders at their minimum, then at their maximum
        for s in at.sidebar.slider:
            s.set_value(s.min if lo_or_hi == 0 else s.max)
        at.run()
        assert not at.exception
        assert "companies match your filters" in at.subheader[0].value


def test_screener_default_shows_all_92():
    assert _screener().subheader[0].value.startswith("92 ")


# ---- Sprint 4 Day 27: 10 tickers across IT / Financials / FMCG / Energy / Healthcare, plus partial-history companies
SPRINT4_TICKERS = ["TCS", "INFY", "HDFCBANK", "SBIN", "HINDUNILVR", "NESTLEIND", "RELIANCE", "NTPC", "SUNPHARMA", "CIPLA"]
PARTIAL_HISTORY = ["JIOFIN", "LICI", "ATGL", "ADANIGREEN"]   # fewer than 10 years of data


@pytest.mark.parametrize("ticker", SPRINT4_TICKERS + PARTIAL_HISTORY)
@pytest.mark.parametrize("page", ["02_profile.py", "05_trends.py", "08_reports.py"])
def test_company_pages_sprint4_tickers(page, ticker):
    at = AppTest.from_file(str(ROOT / "src/dashboard/pages" / page), default_timeout=90)
    at.session_state["ticker"] = ticker
    at.run()
    assert not at.exception


def test_profile_shows_data_available_note_for_short_history():
    at = AppTest.from_file(str(ROOT / "src/dashboard/pages/02_profile.py"), default_timeout=90)
    at.session_state["ticker"] = "JIOFIN"
    at.run()
    assert any("Data available" in i.value for i in at.info)


def test_profile_unknown_ticker_message(monkeypatch):
    at = AppTest.from_file(str(ROOT / "src/dashboard/pages/02_profile.py"), default_timeout=90)
    at.query_params["ticker"] = "NOTREAL"
    at.run()
    assert not at.exception and any("Ticker not found" in w.value for w in at.warning)


@pytest.mark.parametrize("page", ["01_home.py", "04_peers.py", "06_sectors.py", "07_capital.py", "09_valuation.py", "10_cashflow.py"])
def test_universe_pages_render(page):
    assert not AppTest.from_file(str(ROOT / "src/dashboard/pages" / page), default_timeout=90).run().exception
