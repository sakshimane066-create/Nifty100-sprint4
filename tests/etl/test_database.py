"""Acceptance gates verified against the built database (AC-01, 03, 04, 06, 07, 14)."""
import pandas as pd
import pytest

from src.screener.engine import load_config, load_universe, run_preset


def test_ac01_92_companies(conn):
    assert conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0] == 92


def test_ac03_foreign_keys(conn):
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_no_duplicate_annual_keys(conn):
    for t in ("profitandloss", "balancesheet", "cashflow"):
        assert conn.execute(f"SELECT COUNT(*) FROM (SELECT 1 FROM {t} GROUP BY company_id, year HAVING COUNT(*)>1)").fetchone()[0] == 0


def test_years_are_normalised(conn):
    bad = conn.execute("SELECT COUNT(*) FROM profitandloss WHERE year NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'").fetchone()[0]
    assert bad == 0


def test_all_companies_have_ratios(conn):
    assert conn.execute("SELECT COUNT(DISTINCT company_id) FROM financial_ratios").fetchone()[0] == 92


def test_ratios_match_source_table(conn):
    """Engine ROE vs Bluestock pre-computed ROE: >=98% of rows within 2%."""
    m = pd.read_sql("""SELECT r.return_on_equity_pct a, s.return_on_equity_pct b FROM financial_ratios r
                       JOIN financial_ratios_source s USING (company_id, fy)""", conn).dropna()
    assert (((m.a - m.b).abs()) <= (0.02 * m.b.abs()).clip(lower=0.05)).mean() > 0.98


def test_ac07_quality_preset_size(conn):
    cfg = load_config()
    n = len(run_preset(load_universe(conn), "Quality Compounder", cfg))
    assert 10 <= n <= 50


def test_ac07_quality_preset_filters_hold(conn):
    r = run_preset(load_universe(conn), "Quality Compounder")
    assert (r.return_on_equity_pct >= 15).all() and (r.free_cash_flow_cr >= 0).all()


def test_ac14_peer_groups(conn):
    assert conn.execute("SELECT COUNT(DISTINCT peer_group) FROM peer_percentiles").fetchone()[0] == 11


def test_screener_has_18_filters_and_6_presets():
    cfg = load_config()
    assert len(cfg["filters"]) == 18 and len(cfg["presets"]) == 6
