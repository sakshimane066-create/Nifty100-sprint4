import math

import pandas as pd
import pytest

from src.analytics.ratios import cagr, capital_pattern, compute_ratios, debt_to_equity, interest_coverage, roe, safe_div
from src.analytics.peer import percent_rank
from src.screener.engine import _de_score, _icr_score


def test_roe_positive():
    assert roe(100, 400, 100) == pytest.approx(20.0)


def test_roe_negative_equity_is_none():
    assert roe(100, 10, -60) is None


def test_de_debtfree_zero():
    assert debt_to_equity(0, 100, 400) == 0


def test_icr_debtfree_none():
    assert interest_coverage(500, 20, 0) is None
    assert interest_coverage(500, 100, 100) == pytest.approx(6.0)


def test_cagr_normal():
    v, f = cagr(100, 161.05, 5)
    assert v == pytest.approx(10.0, abs=0.01) and f == ""


@pytest.mark.parametrize("base,end,flag", [
    (-100, 200, "TURNAROUND"), (100, -50, "DECLINE_TO_LOSS"), (-100, -50, "BOTH_NEGATIVE"), (0, 10, "ZERO_BASE"), (None, 10, "INSUFFICIENT"),
])
def test_cagr_flags(base, end, flag):
    v, f = cagr(base, end, 5)
    assert v is None and f == flag


def test_safe_div():
    assert safe_div(1, 0) is None and safe_div(None, 2) is None and safe_div(6, 3) == 2


@pytest.mark.parametrize("sig,pay,label", [
    ((1, -1, -1), 10, "Reinvestor"), ((1, -1, -1), 60, "Shareholder Returns"), ((1, -1, 1), 0, "Growth Investor"),
    ((1, 1, -1), 0, "Harvester"), ((1, 1, 1), 0, "Cash Accumulator"), ((-1, -1, 1), 0, "Distress Signal"),
    ((-1, 1, 1), 0, "Distress Signal"), ((-1, -1, -1), 0, "Cash Burn"), ((-1, 1, -1), 0, "Asset Liquidation"),
])
def test_capital_patterns(sig, pay, label):
    assert capital_pattern(*sig, payout=pay) == label


def test_percent_rank_orientation():
    s = pd.Series([1.0, 2.0, 3.0])
    assert percent_rank(s).tolist() == [0.0, 0.5, 1.0]
    assert percent_rank(s, higher_is_better=False).tolist() == [1.0, 0.5, 0.0]


def test_score_curves():
    assert _de_score(0) == 100 and _de_score(1) == 70 and _de_score(6) == 0
    assert _icr_score(float("nan")) == 100 and _icr_score(1.0) == 0 and _icr_score(5) == 75


def _row(**kw):
    base = dict(company_id="X", year="2024-03", fy=2024, broad_sector="IT", sales=1000, expenses=700, operating_profit=300,
                opm_percentage=30, other_income=10, interest=0, depreciation=50, net_profit=200, eps=10, dividend_payout=20,
                equity_capital=10, reserves=490, borrowings=0, other_liabilities=100, fixed_assets=100, investments=50,
                other_asset=400, total_assets=600, cfo=250, cfi=-100, cff=-80, face_value=1)
    base.update(kw)
    return base


def test_compute_ratios_end_to_end():
    r, _ = compute_ratios(pd.DataFrame([_row()]))
    x = r.iloc[0]
    assert x.net_profit_margin_pct == pytest.approx(20) and x.return_on_equity_pct == pytest.approx(40)
    assert x.roce_pct == pytest.approx(50) and x.debt_to_equity == 0 and math.isnan(x.interest_coverage)
    assert x.free_cash_flow_cr == 150 and x.book_value_per_share == pytest.approx(50)
    assert x.capital_allocation == "Reinvestor"


def test_cagr_uses_exact_fiscal_gap_and_flags_turnaround():
    rows = [_row(fy=2019, year="2019-03", net_profit=-50), _row(fy=2024, year="2024-03", net_profit=200)]
    r, log = compute_ratios(pd.DataFrame(rows))
    last = r[r.fy == 2024].iloc[0]
    assert math.isnan(last.pat_cagr_5y) and "pat_5y:TURNAROUND" in last.cagr_flags
    assert any("TURNAROUND" in l for l in log)


def test_scale_suspect_blanks_bs_ratios_but_keeps_pl_ratios():
    r, log = compute_ratios(pd.DataFrame([_row(sales=20000, total_assets=161, equity_capital=11, reserves=73, net_profit=4000)]))
    x = r.iloc[0]
    assert x.bs_scale_suspect == 1 and math.isnan(x.return_on_equity_pct) and math.isnan(x.debt_to_equity)
    assert x.net_profit_margin_pct == pytest.approx(20) and any("BS_SCALE_SUSPECT" in l for l in log)


def test_scale_suspect_nulls_balance_sheet_ratios():
    r, log = compute_ratios(pd.DataFrame([_row(sales=20000, total_assets=160, net_profit=4000, equity_capital=11, reserves=73)]))
    x = r.iloc[0]
    assert x.bs_scale_suspect == 1 and math.isnan(x.return_on_equity_pct) and math.isnan(x.debt_to_equity)
    assert x.net_profit_margin_pct == pytest.approx(20)  # P&L-only ratios survive
    assert any("BS_SCALE_SUSPECT" in l for l in log)


def test_financials_negative_cfo_is_not_distress():
    r, _ = compute_ratios(pd.DataFrame([_row(broad_sector="Financials", cfo=-500, cfi=-100, cff=700),
                                        _row(company_id="Y", broad_sector="IT", cfo=-500, cfi=-100, cff=700)]))
    lab = dict(zip(r.company_id, r.capital_allocation))
    assert lab["X"] == "Lending Growth (Financials)" and lab["Y"] == "Distress Signal"
