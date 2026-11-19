"""Shared DB access and UI helpers for the dashboard (cached, parameterised queries only)."""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DB_PATH = Path(os.getenv("DB_PATH", ROOT / "data" / "nifty100.db"))
if not DB_PATH.is_absolute():
    DB_PATH = ROOT / DB_PATH


@st.cache_resource
def get_conn() -> sqlite3.Connection:
    """Return one shared read connection."""
    return sqlite3.connect(DB_PATH, check_same_thread=False)


@st.cache_data(ttl=600, show_spinner=False)
def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Run a parameterised SELECT and cache the result for 10 minutes."""
    return pd.read_sql(sql, get_conn(), params=params)


def table_exists(name: str) -> bool:
    """True if the table exists (not cached, so a rebuilt database is noticed immediately)."""
    row = get_conn().execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return row is not None


def load_db() -> None:
    """Fail early with a friendly message if the database or its core tables are missing."""
    if not DB_PATH.exists():
        st.error(f"Database not found at {DB_PATH}. Run `python -m src.pipeline` first.")
        st.stop()
    if not table_exists("financial_ratios"):
        st.error("The database is missing its computed tables (the ETL step wipes them). Run `python -m src.pipeline` and restart the app.")
        st.stop()


def page_setup(title: str, icon: str = "📊") -> None:
    """Common page config, DB check and the simulated-data notice."""
    st.set_page_config(page_title="Nifty 100 Analytics", page_icon=icon, layout="wide", initial_sidebar_state="expanded")
    load_db()
    st.sidebar.markdown("### N100 Financial Intelligence")
    st.sidebar.caption("Stock prices, market cap and valuation multiples are **SIMULATED** datasets.")
    st.title(f"{icon} {title}")


def company_picker(label: str = "Company", key: str = "ticker", sidebar: bool = False) -> str:
    """Searchable ticker selector shared across pages (remembers the choice in session state)."""
    df = query("SELECT id, company_name FROM companies ORDER BY company_name")
    opts = df["id"].tolist()
    names = dict(zip(df["id"], df["company_name"]))
    default = opts.index(st.session_state[key]) if st.session_state.get(key) in opts else opts.index("TCS") if "TCS" in opts else 0
    box = st.sidebar if sidebar else st
    pick = box.selectbox(label, opts, index=default, format_func=lambda t: f"{t} — {names[t]}")
    st.session_state[key] = pick
    return pick


def fmt(v: float | None, suffix: str = "", nd: int = 1) -> str:
    """Format a number for KPI tiles; '—' for missing."""
    return "—" if v is None or pd.isna(v) else f"{v:,.{nd}f}{suffix}"


# ---------------------------------------------------------------- named loaders (every one cached for 10 minutes via query())
def get_companies() -> pd.DataFrame:
    """All companies with sector, sub-sector and market-cap category."""
    return query("""SELECT c.id, c.company_name, c.about_company, c.website, c.company_logo, s.broad_sector, s.sub_sector, s.market_cap_category
                    FROM companies c LEFT JOIN sectors s ON s.company_id = c.id ORDER BY c.company_name""")


def get_ratios(ticker: str, year: int | None = None) -> pd.DataFrame:
    """Computed KPIs for one company (all years, or one fiscal year)."""
    if year is None:
        return query("SELECT * FROM financial_ratios WHERE company_id = ? ORDER BY fy", (ticker,))
    return query("SELECT * FROM financial_ratios WHERE company_id = ? AND fy = ?", (ticker, int(year)))


def get_pl(ticker: str) -> pd.DataFrame:
    """Annual profit & loss rows."""
    return query("SELECT * FROM profitandloss WHERE company_id = ? ORDER BY fy", (ticker,))


def get_bs(ticker: str) -> pd.DataFrame:
    """Annual balance sheet rows (interim half-year columns excluded)."""
    return query("SELECT *, equity_capital + reserves AS equity FROM balancesheet WHERE company_id = ? AND year NOT LIKE '%-09' ORDER BY fy", (ticker,))


def get_cf(ticker: str) -> pd.DataFrame:
    """Annual cash-flow rows."""
    return query("SELECT * FROM cashflow WHERE company_id = ? ORDER BY fy", (ticker,))


def get_sectors() -> pd.DataFrame:
    """Company -> sector mapping."""
    return query("SELECT * FROM sectors ORDER BY broad_sector, company_id")


def get_peers(group_name: str) -> pd.DataFrame:
    """Members of a peer group with the benchmark flag."""
    return query("SELECT * FROM peer_groups WHERE peer_group_name = ? ORDER BY is_benchmark DESC, company_id", (group_name,))


def get_valuation(ticker: str) -> pd.DataFrame:
    """Simulated valuation multiples by year for one company."""
    return query("SELECT * FROM market_cap WHERE company_id = ? ORDER BY year", (ticker,))
