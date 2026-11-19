import numpy as np
import pandas as pd
import pytest

from src.nlp import parser, pros_cons, sentiment, tagger


@pytest.mark.parametrize("raw,exp", [
    ("10 Years: 21%", ("10Y", 10, 21.0)), ("5 Years:       22%", ("5Y", 5, 22.0)), ("5 Years          14%", ("5Y", 5, 14.0)),
    ("TTM:            47%", ("TTM", None, 47.0)), ("1 Year:        -2%", ("1Y", 1, -2.0)), ("Last Year:    17%", ("LastYear", 1, 17.0)),
    ("3 Years: 12.5%", ("3Y", 3, 12.5)),
])
def test_parse_cell_variants(raw, exp):
    assert parser.parse_cell(raw) == exp


@pytest.mark.parametrize("raw", ["garbage", "10 Years", "", None, 42, "about 5 years 10%"])
def test_parse_cell_rejects(raw):
    assert parser.parse_cell(raw) is None


def test_unknown_format_is_logged():
    df = pd.DataFrame({"company_id": ["X"], "compounded_sales_growth": ["N/A"], "compounded_profit_growth": ["5 Years: 9%"],
                       "stock_price_cagr": [None], "roe": [None]})
    ok, bad = parser.parse_analysis(df)
    assert len(ok) == 1 and len(bad) == 1 and bad.iloc[0]["raw"] == "N/A"


def test_cross_validation_flags_large_gap():
    parsed = pd.DataFrame([dict(company_id="A", metric_type="sales_growth_cagr", period="3Y", period_years=3, value_pct=5.0)])
    ratios = pd.DataFrame([dict(company_id="A", fy=2024, revenue_cagr_3y=15.0, pat_cagr_3y=1.0, return_on_equity_pct=10.0)])
    cv = parser.cross_validate(parsed, ratios)
    assert cv.iloc[0]["flag"] == "DIVERGES" and cv.iloc[0]["diff_pts"] == 10.0


def test_tagger_word_boundary_and_validation():
    assert tagger.tag_description("A leading private sector bank offering loans")[0] == "Financials"
    assert tagger.tag_description("Sells soil conditioners")[0] != "Energy"  # 'oil' must not match inside 'soil'
    assert tagger.tag_description(None)[0] is None
    rep = tagger.validation_report(pd.DataFrame({"id": ["A"], "about_company": ["pharmaceutical company"]}),
                                   pd.DataFrame({"company_id": ["A"], "broad_sector": ["Healthcare"]}))
    assert rep.iloc[0]["match"] == 1


def test_sentiment_range_and_blank():
    assert -1 <= sentiment.score("Company has a good track record") <= 1
    assert sentiment.score("") == 0.0 and sentiment.score(None) == 0.0


def _f(**kw):
    base = dict(company_id="X", is_financial=0, years=12, roe3=np.nan, roe3_min=np.nan, fcf_pos_5y=0, cfo_pat_5y=np.nan, payout3=np.nan, payout_latest=np.nan,
                opm_change_3y=np.nan, rev_up_5y=0, other_income_share=np.nan, roce_pct=np.nan, debt_to_equity=np.nan, revenue_cagr_5y=np.nan,
                pat_cagr_5y=np.nan, net_profit_margin_pct=np.nan, interest_coverage=np.nan, fcf_concern=0, capital_allocation="Reinvestor",
                net_profit_cr=100.0, return_on_equity_pct=np.nan)
    base.update(kw)
    return base


def _gen(rows, sectors=None):
    feats = pd.DataFrame(rows)
    sec = pd.Series({r["company_id"]: "S" for r in rows}) if sectors is None else sectors
    return pros_cons.generate(feats, sec)


def test_there_are_12_pro_and_12_con_rules():
    assert len(pros_cons.PRO_RULES) == 12 and len(pros_cons.CON_RULES) == 12


def test_strong_company_gets_expected_pros():
    out = _gen([_f(roe3=30, roe3_min=25, roce_pct=40, debt_to_equity=0.0, revenue_cagr_5y=20, fcf_pos_5y=1)])
    ids = set(out[out.type == "pro"].rule_triggered)
    assert {"P01_ROE_TRACK_RECORD", "P02_HIGH_ROCE", "P03_DEBT_FREE", "P04_REVENUE_GROWTH", "P06_FCF_POSITIVE_5Y"} <= ids


def test_weak_company_gets_expected_cons():
    out = _gen([_f(roe3=4, debt_to_equity=3.5, interest_coverage=1.2, fcf_concern=1, capital_allocation="Distress Signal")])
    ids = set(out[out.type == "con"].rule_triggered)
    assert {"C01_LOW_ROE", "C02_HIGH_LEVERAGE", "C03_LOW_INTEREST_COVER", "C04_NEGATIVE_FCF_3Y", "C11_DISTRESS_PATTERN"} <= ids


def test_financials_skip_non_financial_rules():
    out = _gen([_f(is_financial=1, debt_to_equity=9.0, roce_pct=60.0)])
    assert not out.rule_triggered.isin(["C02_HIGH_LEVERAGE", "P02_HIGH_ROCE"]).any()


def test_every_company_gets_at_least_one_pro_and_con_with_confidence_over_60():
    out = _gen([_f(), _f(company_id="Y")])  # no inputs at all -> fallbacks
    g = out.groupby(["company_id", "type"]).size().unstack(fill_value=0)
    assert (g.pro >= 1).all() and (g.con >= 1).all() and (out.confidence_pct > 60).all()


def test_max_five_per_side():
    out = _gen([_f(roe3=40, roe3_min=30, roce_pct=60, debt_to_equity=0, revenue_cagr_5y=40, pat_cagr_5y=50, fcf_pos_5y=1, cfo_pat_5y=2, net_profit_margin_pct=40,
                   payout3=50, interest_coverage=50, opm_change_3y=9, rev_up_5y=1)])
    assert (out.type == "pro").sum() == 5


# ---- database-level acceptance (AC-16)
def test_ac16_generated_coverage(conn):
    pc = pd.read_sql("SELECT * FROM pros_cons_generated", conn)
    g = pc.groupby(["company_id", "type"]).size().unstack(fill_value=0)
    assert len(g) == 92 and (g.pro >= 1).all() and (g.con >= 1).all()
    assert (pc.confidence_pct > 60).all()


def test_analysis_parsed_has_no_failures(conn):
    parsed, bad = parser.parse_analysis(pd.read_sql("SELECT * FROM analysis", conn))
    assert len(parsed) == 64 and bad.empty
