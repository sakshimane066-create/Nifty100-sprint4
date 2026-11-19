import pandas as pd

from src.etl import validator as v


def test_dq01_dup_company():
    assert len(v.dq01_company_pk(pd.DataFrame({"id": ["A", "A", "B"]}))) == 2


def test_dq02_dup_year_keeps_last():
    df = pd.DataFrame({"company_id": ["A", "A"], "year": ["2023-03"] * 2})
    assert len(v.dq02_annual_pk(df, "t")) == 1


def test_dq03_orphan():
    f = v.dq03_fk(pd.DataFrame({"company_id": ["A", "ZZ"]}), "t", {"A"})
    assert len(f) == 1 and f[0]["severity"] == "CRITICAL"


def test_dq04_bs_balance():
    f = v.dq04_bs_balance(pd.DataFrame({"company_id": ["A"], "year": ["2023-03"], "total_assets": [1000], "total_liabilities": [1020]}))
    assert len(f) == 1 and f[0]["severity"] == "WARNING"


def test_dq05_opm_mismatch():
    df = pd.DataFrame({"company_id": ["A"], "year": ["y"], "sales": [100], "operating_profit": [20], "opm_percentage": [35]})
    assert len(v.dq05_opm(df)) == 1


def test_dq06_zero_sales():
    assert len(v.dq06_positive_sales(pd.DataFrame({"company_id": ["A"], "year": ["y"], "sales": [0]}))) == 1


def test_dq07_year_format():
    assert len(v.dq07_year_format(pd.DataFrame({"company_id": ["A", "B"], "year": ["2023-03", "PARSE_ERROR"]}), "t")) == 1


def test_dq08_ticker():
    df = pd.DataFrame({"company_id": ["TCS", "tcs", "X", "VERYLONGTICKER1"]})
    assert len(v.dq08_ticker_format(df, "t")) == 3


def test_dq09_net_cash():
    df = pd.DataFrame({"company_id": ["A"], "year": ["y"], "operating_activity": [100], "investing_activity": [-50], "financing_activity": [-20], "net_cash_flow": [100]})
    assert len(v.dq09_net_cash(df)) == 1


def test_dq10_to_12_and_14():
    assert len(v.dq10_fixed_assets(pd.DataFrame({"company_id": ["A"], "year": ["y"], "fixed_assets": [-1]}))) == 1
    assert len(v.dq11_tax_range(pd.DataFrame({"company_id": ["A", "B"], "year": ["y"] * 2, "tax_percentage": [25, 75]}))) == 1
    assert len(v.dq12_payout_cap(pd.DataFrame({"company_id": ["A"], "year": ["y"], "dividend_payout": [250]}))) == 1
    assert len(v.dq14_eps_sign(pd.DataFrame({"company_id": ["A"], "year": ["y"], "net_profit": [10], "eps": [-1]}))) == 1


def test_dq13_url():
    d = pd.DataFrame({"company_id": ["A", "B"], "year": [2024, 2024], "annual_report": ["ok", "bad"]})
    assert len(v.dq13_url(d, {"ok": 200, "bad": 404})) == 1


def test_dq15_info_and_dq16_coverage():
    f = v.dq15_strict_balance(pd.DataFrame({"company_id": ["A"], "year": ["y"], "total_assets": [10], "total_liabilities": [11]}))
    assert f[0]["severity"] == "INFO"
    pl = pd.DataFrame({"company_id": ["A"] * 3 + ["B"] * 6, "year": range(9)})
    assert len(v.dq16_coverage(pl, pl, pl)) == 3  # A short in all three tables


def test_dq17_bs_scale():
    pl = pd.DataFrame({"company_id": ["A", "B"], "year": ["2024-03"] * 2, "sales": [20000, 1000]})
    bs = pd.DataFrame({"company_id": ["A", "B"], "year": ["2024-03"] * 2, "total_assets": [161, 900]})
    f = v.dq17_bs_scale(pl, bs)
    assert len(f) == 1 and f[0]["company_id"] == "A"

