"""Data-quality rules DQ-01..DQ-16. Each rule returns a list of failure dicts."""
from __future__ import annotations

import re

import pandas as pd

CRITICAL, WARNING, INFO = "CRITICAL", "WARNING", "INFO"
COLUMNS = ["rule_id", "severity", "table", "company_id", "year", "field", "issue", "action"]
_YEAR_RE = re.compile(r"^\d{4}-\d{2}$")


def _fail(rule, sev, table, df, field, issue, action) -> list[dict]:
    """Build failure records for every row of df."""
    out = []
    for _, r in df.iterrows():
        out.append(
            dict(rule_id=rule, severity=sev, table=table, company_id=r.get("company_id", r.get("id")),
                 year=r.get("year"), field=field, issue=issue, action=action)
        )
    return out


def dq01_company_pk(companies: pd.DataFrame) -> list[dict]:
    """DQ-01: companies.id must be unique."""
    d = companies[companies["id"].duplicated(keep=False)]
    return _fail("DQ-01", CRITICAL, "companies", d, "id", "duplicate ticker", "halt load")


def dq02_annual_pk(df: pd.DataFrame, table: str) -> list[dict]:
    """DQ-02: no duplicate (company_id, year)."""
    d = df[df.duplicated(["company_id", "year"], keep="last")]
    return _fail("DQ-02", CRITICAL, table, d, "company_id,year", "duplicate annual row", "kept last occurrence")


def dq03_fk(df: pd.DataFrame, table: str, valid_ids: set) -> list[dict]:
    """DQ-03: every company_id must exist in companies."""
    d = df[~df["company_id"].isin(valid_ids)]
    return _fail("DQ-03", CRITICAL, table, d, "company_id", "orphan ticker not in companies.xlsx", "row rejected")


def dq04_bs_balance(bs: pd.DataFrame) -> list[dict]:
    """DQ-04: |assets - liabilities| / assets < 1%."""
    ta = bs["total_assets"].replace(0, float("nan"))
    d = bs[((bs["total_assets"] - bs["total_liabilities"]).abs() / ta) >= 0.01]
    return _fail("DQ-04", WARNING, "balancesheet", d, "total_assets", "balance sheet does not balance", "flagged, kept")


def dq05_opm(pl: pd.DataFrame) -> list[dict]:
    """DQ-05: source OPM within 1 point of operating_profit / sales."""
    comp = pl["operating_profit"] / pl["sales"].replace(0, float("nan")) * 100
    d = pl[(pl["opm_percentage"] - comp).abs() >= 1.0]
    return _fail("DQ-05", WARNING, "profitandloss", d, "opm_percentage", "source OPM differs from computed",
                 "computed OPM used by ratio engine")


def dq06_positive_sales(pl: pd.DataFrame) -> list[dict]:
    """DQ-06: sales must be > 0."""
    d = pl[pl["sales"] <= 0]
    return _fail("DQ-06", WARNING, "profitandloss", d, "sales", "sales <= 0", "excluded from CAGR")


def dq07_year_format(df: pd.DataFrame, table: str) -> list[dict]:
    """DQ-07: normalised year must be YYYY-MM."""
    d = df[~df["year"].astype(str).str.match(_YEAR_RE)]
    return _fail("DQ-07", CRITICAL, table, d, "year", "unparseable year label", "row rejected")


def dq08_ticker_format(df: pd.DataFrame, table: str) -> list[dict]:
    """DQ-08: ticker must be 2-12 chars, stripped and upper-case."""
    t = df["company_id"].astype(str)
    d = df[(t.str.len() < 2) | (t.str.len() > 12) | (t != t.str.strip().str.upper())]
    return _fail("DQ-08", CRITICAL, table, d, "company_id", "bad ticker format", "row rejected")


def dq09_net_cash(cf: pd.DataFrame) -> list[dict]:
    """DQ-09: net_cash_flow within 10 Cr of CFO+CFI+CFF."""
    s = cf["operating_activity"] + cf["investing_activity"] + cf["financing_activity"]
    d = cf[(cf["net_cash_flow"] - s).abs() > 10]
    return _fail("DQ-09", WARNING, "cashflow", d, "net_cash_flow", "net cash != sum of components",
                 "recomputed from components")


def dq10_fixed_assets(bs: pd.DataFrame) -> list[dict]:
    """DQ-10: fixed_assets >= 0."""
    d = bs[bs["fixed_assets"] < 0]
    return _fail("DQ-10", WARNING, "balancesheet", d, "fixed_assets", "negative fixed assets", "coerced to 0")


def dq11_tax_range(pl: pd.DataFrame) -> list[dict]:
    """DQ-11: 0 <= tax_percentage <= 60."""
    d = pl[(pl["tax_percentage"] < 0) | (pl["tax_percentage"] > 60)]
    return _fail("DQ-11", WARNING, "profitandloss", d, "tax_percentage", "tax rate outside 0-60", "flagged")


def dq12_payout_cap(pl: pd.DataFrame) -> list[dict]:
    """DQ-12: dividend_payout <= 200."""
    d = pl[pl["dividend_payout"] > 200]
    return _fail("DQ-12", WARNING, "profitandloss", d, "dividend_payout", "payout > 200%", "flagged")


def dq13_url(docs: pd.DataFrame, status_by_url: dict[str, int]) -> list[dict]:
    """DQ-13: annual-report URL returns 200 (status map supplied by caller; opt-in network check)."""
    d = docs[docs["annual_report"].map(lambda u: status_by_url.get(u, 200) != 200)]
    return _fail("DQ-13", WARNING, "documents", d, "annual_report", "URL not reachable", "kept, logged")


def dq14_eps_sign(pl: pd.DataFrame) -> list[dict]:
    """DQ-14: eps > 0 when net_profit > 0."""
    d = pl[(pl["net_profit"] > 0) & (pl["eps"] <= 0)]
    return _fail("DQ-14", WARNING, "profitandloss", d, "eps", "EPS sign inconsistent with profit", "flagged")


def dq15_strict_balance(bs: pd.DataFrame) -> list[dict]:
    """DQ-15: strict equality assets == liabilities (INFO counter)."""
    d = bs[bs["total_assets"] != bs["total_liabilities"]]
    return _fail("DQ-15", INFO, "balancesheet", d, "total_assets", "not strictly equal", "counted in audit")


def dq16_coverage(pl: pd.DataFrame, bs: pd.DataFrame, cf: pd.DataFrame) -> list[dict]:
    """DQ-16: each company has >= 5 years in P&L, BS and CF."""
    out = []
    for name, df in (("profitandloss", pl), ("balancesheet", bs), ("cashflow", cf)):
        n = df.groupby("company_id").size()
        d = pd.DataFrame({"company_id": n[n < 5].index})
        out += _fail("DQ-16", WARNING, name, d, "years", "< 5 years of history", "excluded from CAGR if < 3")
    return out


SCALE_MAX_TURNOVER = 8.0


def dq17_bs_scale(pl: pd.DataFrame, bs: pd.DataFrame) -> list[dict]:
    """DQ-17 (added): sales / total_assets > 8x means the balance sheet is on a different scale than the P&L."""
    m = pl[["company_id", "year", "sales"]].merge(bs[["company_id", "year", "total_assets"]], on=["company_id", "year"])
    d = m[(m["total_assets"] > 0) & (m["sales"] / m["total_assets"] > SCALE_MAX_TURNOVER)]
    return _fail("DQ-17", WARNING, "balancesheet", d, "total_assets", "balance sheet scale inconsistent with P&L (asset turnover > 8x)",
                 "balance-sheet ratios set to NULL")


def dq18_swapped_ops(bad_rows: pd.DataFrame) -> list[dict]:
    """DQ-18 (added): operating_profit / opm_percentage columns swapped in the source (rows supplied by etl.repair)."""
    return _fail("DQ-18", WARNING, "profitandloss", bad_rows, "operating_profit",
                 "operating_profit holds expenses and opm_percentage holds operating profit", "columns swapped back")


def dq19_overrides(log: pd.DataFrame) -> list[dict]:
    """DQ-19 (added): a documented source-data override from config/company_overrides.yaml was applied."""
    out = []
    for _, r in log.iterrows():
        out.append(dict(rule_id="DQ-19", severity=INFO, table="companies/sectors", company_id=r["company_id"], year=None,
                        field=r["field"], issue=f"source value overridden: {r['old']!r}", action=f"set to {r['new']!r}"))
    return out


def to_frame(failures: list[dict]) -> pd.DataFrame:
    """Return the failure list as a DataFrame with the standard columns."""
    return pd.DataFrame(failures, columns=COLUMNS)
