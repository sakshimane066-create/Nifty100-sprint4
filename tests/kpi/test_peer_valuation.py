import sqlite3

import pandas as pd
import pytest

from src.analytics.peer import compute_peer_percentiles, peer_flags
from src.analytics.valuation import build_valuation, export_valuation, pe_flag


def test_pe_flag():
    assert pe_flag(40, 20) == "Caution" and pe_flag(10, 20) == "Discount" and pe_flag(20, 20) == "Fair" and pe_flag(float("nan"), 20) == "N/A"


def test_best_in_class_and_watch_flags():
    cols = ["return_on_equity_pct", "roce_pct", "net_profit_margin_pct", "operating_profit_margin_pct", "debt_to_equity",
            "interest_coverage", "fcf_conversion_pct", "revenue_cagr_5y", "pat_cagr_5y", "eps_cagr_5y"]
    ratios = pd.DataFrame({"company_id": list("ABC"), "fy": 2024})
    for c in cols:
        ratios[c] = [3.0, 2.0, 1.0] if c != "debt_to_equity" else [1.0, 2.0, 3.0]  # A best everywhere, C worst
    groups = pd.DataFrame({"peer_group_name": "G", "company_id": list("ABC"), "is_benchmark": [1, 0, 0]})
    fl = peer_flags(compute_peer_percentiles(ratios, groups)).set_index("company_id")
    assert fl.loc["A", "best_in_class"] == 1 and fl.loc["C", "watch_list"] == 1 and fl.loc["B", "best_in_class"] == 0


def test_valuation_build_and_export(conn, tmp_path):
    v = build_valuation(conn)
    assert len(v) == 92 and set(v.pe_flag) <= {"Fair", "Caution", "Discount", "N/A"}
    export_valuation(v, tmp_path)
    assert (tmp_path / "valuation_summary.xlsx").stat().st_size > 5000 and (tmp_path / "valuation_flags.csv").exists()
    cols = ["company_id", "company_name", "sector", "P/E", "P/B", "EV/EBITDA", "FCF_yield_pct", "5yr_median_PE", "PE_vs_sector_median_pct", "flag"]
    x = pd.read_excel(tmp_path / "valuation_summary.xlsx", sheet_name="Valuation", keep_default_na=False)
    assert list(x.columns[:10]) == cols and len(x) == 92          # spec Day 26: exact required columns, 92 rows
    assert set(x["flag"]) <= {"Caution", "Discount", "Fair", "N/A"}
    f = pd.read_csv(tmp_path / "valuation_flags.csv")
    assert set(f["pe_flag"]) <= {"Caution", "Discount"} and len(f) > 0
