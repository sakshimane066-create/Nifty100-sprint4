import sqlite3

import pandas as pd
import pytest

from src.analytics.peer import build_peers
from src.analytics.ratios import build_ratios
from src.etl import loader


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    d = tmp_path_factory.mktemp("etl")
    summary = loader.build_database(d / "t.db", d)
    build_ratios(d / "t.db", d)
    build_peers(d / "t.db")
    return d, summary


def test_orphans_rejected_and_logged(built):
    d, s = built
    f = pd.read_csv(d / "validation_failures.csv")
    orphans = f[f.rule_id == "DQ-03"].company_id.unique()
    assert {"WIPRO", "ZOMATO", "VEDL"} <= set(orphans)
    assert set(f.severity) <= {"CRITICAL", "WARNING", "INFO"}
    assert s["tables"]["companies"] == 92


def test_audit_has_all_tables(built):
    d, _ = built
    a = pd.read_csv(d / "load_audit.csv")
    assert {"companies", "profitandloss", "balancesheet", "cashflow", "documents", "peer_groups"} <= set(a.table)
    assert (a.rejected >= 0).all()


def test_ttm_routed_to_own_table(built):
    d, _ = built
    with sqlite3.connect(d / "t.db") as c:
        assert c.execute("SELECT COUNT(*) FROM profitandloss WHERE year='TTM'").fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM profitandloss_ttm").fetchone()[0] > 80


def test_ticker_alias_repairs_atgl_cashflow(built):
    d, _ = built
    with sqlite3.connect(d / "t.db") as c:
        assert c.execute("SELECT COUNT(*) FROM cashflow WHERE company_id='ATGL'").fetchone()[0] == 7


def test_ratio_outputs_written(built):
    d, _ = built
    assert (d / "capital_allocation.csv").exists() and (d / "ratio_edge_cases.log").exists()


def test_read_excel_header_conventions():
    assert "company_id" in loader.read_excel("profitandloss").columns  # header=1 (banner row)
    assert "company_id" in loader.read_excel("sectors").columns        # header=0
