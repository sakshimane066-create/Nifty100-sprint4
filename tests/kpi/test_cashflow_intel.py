import numpy as np
import pandas as pd
import pytest

from src.analytics import cashflow_intel as ci


@pytest.mark.parametrize("x,exp", [(1.2, "High Quality Earnings"), (0.3, "Accrual Risk"), (0.8, "Moderate"), (None, "Insufficient data"), (np.nan, "Insufficient data")])
def test_cfo_quality(x, exp):
    assert ci.cfo_quality(x) == exp


@pytest.mark.parametrize("x,exp", [(2.0, "Light"), (5.0, "Moderate"), (12.0, "Heavy"), (None, "Insufficient data")])
def test_capex_category(x, exp):
    assert ci.capex_category(x) == exp


@pytest.mark.parametrize("x,exp", [(75, "Efficient"), (45, "Moderate"), (10, "CapEx Heavy"), (None, "Insufficient data")])
def test_fcf_tier(x, exp):
    assert ci.fcf_tier(x) == exp


def test_deleveraging_and_distress():
    assert ci.is_deleveraging(-50, 80, 100) and not ci.is_deleveraging(-50, 120, 100) and not ci.is_deleveraging(20, 80, 100)
    assert ci.is_distress(-10, 30) and not ci.is_distress(10, 30) and not ci.is_distress(-10, -5)
    assert not ci.is_distress(np.nan, 5)


def _hist(cfo, cff, fin=0, fcf=None):
    n = len(cfo)
    return pd.DataFrame(dict(company_id="X", fy=range(2024 - n + 1, 2025), year="y", is_financial=fin, sales_cr=1000.0, operating_profit_cr=200.0, net_profit_cr=100.0,
                             cfo=cfo, fcf=fcf if fcf is not None else cfo, capex_cr=50.0, capex_intensity_pct=5.0, total_debt_cr=100.0, capital_allocation="Reinvestor",
                             cfi=-50.0, cff=cff))


def test_distress_company_is_alerted_and_financial_is_not():
    rows, alerts = ci.build_intelligence(_hist([100, 100, 100, -20, -30], [-5, -5, -5, 40, 50]))
    assert rows.iloc[0]["distress_latest"] == 1 and rows.iloc[0]["distress_years_3y"] == 2 and len(alerts) == 2
    rows_f, alerts_f = ci.build_intelligence(_hist([100, 100, 100, -20, -30], [-5, -5, -5, 40, 50], fin=1))
    assert rows_f.iloc[0]["distress_latest"] == 0 and alerts_f.empty and rows_f.iloc[0]["cfo_quality"] == ci.NA_FIN


def test_quality_labels_from_history():
    rows, _ = ci.build_intelligence(_hist([150] * 5, [-5] * 5))
    assert rows.iloc[0]["cfo_quality"] == "High Quality Earnings" and rows.iloc[0]["cfo_pat_5y"] == 1.5


def test_cashflow_intelligence_table_complete(conn):
    d = pd.read_sql("SELECT * FROM cashflow_intelligence", conn)
    assert len(d) == 92 and d.company_id.is_unique
