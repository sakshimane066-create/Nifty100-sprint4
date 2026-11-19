import pytest

from src.etl.normaliser import PARSE_ERROR, fiscal_year, normalize_ticker, normalize_year, period_months


@pytest.mark.parametrize("raw,exp", [
    ("Mar 2023", "2023-03"), ("Mar-23", "2023-03"), ("Mar 23", "2023-03"), ("March-2023", "2023-03"),
    ("Dec 2012", "2012-12"), ("Dec-22", "2022-12"), ("Jun 2013", "2013-06"), ("Sep 2024", "2024-09"),
    (2023, "2023-03"), ("2023", "2023-03"), (2013.0, "2013-03"), ("FY23", "2023-03"), ("FY2024", "2024-03"),
    ("2023-03", "2023-03"), ("  mar 2016  ", "2016-03"), ("Mar 2016 9m", "2016-03"), ("Mar 2023 15", "2023-03"),
    ("TTM", "TTM"),
])
def test_year_ok(raw, exp):
    assert normalize_year(raw) == exp


@pytest.mark.parametrize("raw", ["xyz", "", None, float("nan"), "2024.5", "Foo 2023", "13-2023"])
def test_year_garbage(raw):
    assert normalize_year(raw) == PARSE_ERROR


def test_period_months():
    assert period_months("Mar 2016 9m") == 9
    assert period_months("Mar 2023 15") == 15
    assert period_months("Mar 2023") == 12


def test_fiscal_year():
    assert fiscal_year("2023-03") == 2023
    assert fiscal_year("TTM") is None


@pytest.mark.parametrize("raw,exp", [
    ("TCS", "TCS"), (" tcs ", "TCS"), ("BAJAJ-AUTO", "BAJAJ-AUTO"), ("M&M", "M&M"), ("agtl", "ATGL"), (None, ""),
])
def test_ticker(raw, exp):
    assert normalize_ticker(raw) == exp
