import pandas as pd

from src.etl.repair import repair_swapped_ops, swapped_ops_mask


def _pl(**kw):
    base = dict(company_id="HEROMOTOCO", year="2024-03", sales=37789.0, operating_profit=32554.0, opm_percentage=5235.0)
    base.update(kw)
    return pd.DataFrame([base])


def test_swapped_row_is_detected_and_repaired():
    fixed, bad = repair_swapped_ops(_pl())
    assert len(bad) == 1
    assert fixed.loc[0, "operating_profit"] == 5235.0
    assert abs(fixed.loc[0, "opm_percentage"] - 13.85) < 0.01


def test_normal_row_untouched():
    df = _pl(operating_profit=5235.0, opm_percentage=13.85)
    fixed, bad = repair_swapped_ops(df)
    assert bad.empty and fixed.equals(df)


def test_real_percentage_never_flagged():
    assert not swapped_ops_mask(_pl(operating_profit=500.0, opm_percentage=45.0)).any()


def test_small_amount_swap_is_caught():
    """HDFCLIFE FY23: opm_percentage = 80 (an amount < 100) but sales - operating_profit == 80."""
    df = _pl(company_id="HDFCLIFE", sales=70207.0, operating_profit=70127.0, opm_percentage=80.0)
    fixed, bad = repair_swapped_ops(df)
    assert len(bad) == 1 and fixed.loc[0, "operating_profit"] == 80.0


def test_consistent_row_with_small_expenses_not_flagged():
    assert not swapped_ops_mask(_pl(sales=1000.0, operating_profit=20.0, opm_percentage=2.0)).any()


def test_overrides_applied_and_logged():
    from src.etl.repair import apply_overrides
    comp = pd.DataFrame({"id": ["LT", "TCS"], "about_company": ["Lithuania is a country", "TCS text"]})
    sec = pd.DataFrame({"company_id": ["ABB", "TCS"], "broad_sector": ["Industrials", "IT"], "sub_sector": ["Capital Goods", "IT Services"]})
    c2, s2, log = apply_overrides(comp, sec)
    assert "Larsen" in c2.loc[c2.id == "LT", "about_company"].iloc[0] and c2.loc[c2.id == "TCS", "about_company"].iloc[0] == "TCS text"
    assert s2.loc[s2.company_id == "ABB", "broad_sector"].iloc[0] == "Healthcare" and len(log) == 3
