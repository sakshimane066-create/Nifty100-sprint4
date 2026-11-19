"""Financial ratio engine: pure KPI functions + a DB-level engine writing `financial_ratios`."""
from __future__ import annotations

import logging
import math
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "nifty100.db"
FLAG_OK = ""
BS_SCALE_MAX_TURNOVER = 8.0
BS_DERIVED = ["return_on_equity_pct", "roce_pct", "roa_pct", "debt_to_equity", "asset_turnover", "fixed_asset_turnover",
              "working_capital_days", "net_debt_cr", "net_debt_to_ebitda", "book_value_per_share"]


# ---------------------------------------------------------------- pure functions
def safe_div(num: float | None, den: float | None) -> float | None:
    """Return num/den, or None when either is missing or den is 0."""
    if num is None or den is None or pd.isna(num) or pd.isna(den) or den == 0:
        return None
    return num / den


def roe(net_profit: float, equity: float, reserves: float) -> float | None:
    """ROE % = net_profit / (equity + reserves) x 100; None if total equity <= 0."""
    eq = equity + reserves
    return None if eq <= 0 else net_profit / eq * 100


def debt_to_equity(borrowings: float, equity: float, reserves: float) -> float | None:
    """D/E = borrowings / (equity + reserves); 0 for debt-free; None if equity <= 0."""
    eq = equity + reserves
    return None if eq <= 0 else borrowings / eq


def interest_coverage(op_profit: float, other_income: float, interest: float) -> float | None:
    """ICR = (op_profit + other_income) / interest; None when interest is 0 (debt-free)."""
    return None if not interest else (op_profit + (other_income or 0)) / interest


def cagr(base: float | None, end: float | None, n: int) -> tuple[float | None, str]:
    """CAGR % between two values over n years, with the edge-case flag from the decision table."""
    if base is None or end is None or pd.isna(base) or pd.isna(end):
        return None, "INSUFFICIENT"
    if base == 0:
        return None, "ZERO_BASE"
    if base < 0:
        return None, "TURNAROUND" if end > 0 else "BOTH_NEGATIVE"
    if end < 0:
        return None, "DECLINE_TO_LOSS"
    return ((end / base) ** (1 / n) - 1) * 100, FLAG_OK


def capital_pattern(cfo: float, cfi: float, cff: float, payout: float | None = None) -> str:
    """Label the CFO/CFI/CFF sign pattern (8 patterns; (+,-,-) split by dividend payout)."""
    if any(x is None or pd.isna(x) for x in (cfo, cfi, cff)):
        return "Unknown"
    key = (cfo >= 0, cfi >= 0, cff >= 0)
    if key == (True, False, False):
        return "Shareholder Returns" if (payout or 0) >= 40 else "Reinvestor"
    return {
        (True, False, True): "Growth Investor",
        (True, True, False): "Harvester",
        (True, True, True): "Cash Accumulator",
        (False, False, True): "Distress Signal",
        (False, True, True): "Distress Signal",
        (False, False, False): "Cash Burn",
        (False, True, False): "Asset Liquidation",
    }[key]


# ---------------------------------------------------------------- engine
def _load(conn: sqlite3.Connection) -> pd.DataFrame:
    q = """
    SELECT p.company_id, p.year, p.fy, p.sales, p.expenses, p.operating_profit, p.opm_percentage, p.other_income,
           p.interest, p.depreciation, p.net_profit, p.eps, p.dividend_payout,
           b.equity_capital, b.reserves, b.borrowings, b.other_liabilities, b.fixed_assets, b.investments,
           b.other_asset, b.total_assets,
           c.operating_activity AS cfo, c.investing_activity AS cfi, c.financing_activity AS cff,
           co.face_value, s.broad_sector
    FROM profitandloss p
    LEFT JOIN balancesheet b USING (company_id, year)
    LEFT JOIN cashflow c USING (company_id, year)
    JOIN companies co ON co.id = p.company_id
    LEFT JOIN sectors s ON s.company_id = p.company_id
    ORDER BY p.company_id, p.fy"""
    return pd.read_sql(q, conn)


def _growth(df: pd.DataFrame, col: str, n: int, label: str, log: list) -> tuple[pd.Series, pd.Series]:
    """CAGR of `col` over n fiscal years, matched on (company_id, fy - n)."""
    base = df[["company_id", "fy", col]].copy()
    base["fy"] = base["fy"] + n
    m = df[["company_id", "fy", col]].merge(base, on=["company_id", "fy"], how="left", suffixes=("", "_base"))
    vals, flags = [], []
    for cid, fy, end, b in zip(m["company_id"], m["fy"], m[col], m[f"{col}_base"]):
        v, f = cagr(b, end, n)
        vals.append(v)
        flags.append(f)
        if f in ("TURNAROUND", "DECLINE_TO_LOSS", "BOTH_NEGATIVE", "ZERO_BASE"):
            log.append(f"{cid} FY{fy} {label}: {f} (base={b}, end={end})")
    return pd.Series(vals, index=df.index, dtype="float"), pd.Series(flags, index=df.index)


def compute_ratios(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Compute all KPIs for every company-year row of the merged P&L/BS/CF frame."""
    df = df.sort_values(["company_id", "fy"]).drop_duplicates(["company_id", "fy"], keep="last").reset_index(drop=True)
    log: list[str] = []
    r = df[["company_id", "year", "fy", "broad_sector"]].copy()
    r["is_financial"] = (df["broad_sector"] == "Financials").astype(int)
    eq = df["equity_capital"] + df["reserves"]
    sales = df["sales"].where(df["sales"] > 0)
    ebit = df["operating_profit"] - df["depreciation"].fillna(0)
    ta = df["total_assets"].where(df["total_assets"] > 0)

    r["net_profit_margin_pct"] = df["net_profit"] / sales * 100
    r["operating_profit_margin_pct"] = df["operating_profit"] / sales * 100  # computed (source OPM unreliable for banks)
    r["ebit_margin_pct"] = ebit / sales * 100
    r["return_on_equity_pct"] = (df["net_profit"] / eq.where(eq > 0)) * 100
    r["roce_pct"] = ebit / (eq + df["borrowings"]).where((eq + df["borrowings"]) > 0) * 100
    r["roa_pct"] = df["net_profit"] / ta * 100
    r["debt_to_equity"] = df["borrowings"] / eq.where(eq > 0)
    r["interest_coverage"] = (df["operating_profit"] + df["other_income"].fillna(0)) / df["interest"].where(df["interest"] > 0)
    r["asset_turnover"] = df["sales"] / ta
    r["fixed_asset_turnover"] = df["sales"] / df["fixed_assets"].where(df["fixed_assets"] > 0)
    r["working_capital_days"] = (df["other_asset"] - df["other_liabilities"]) / sales * 365
    r["net_debt_cr"] = df["borrowings"] - df["investments"].fillna(0)
    r["net_debt_to_ebitda"] = r["net_debt_cr"] / df["operating_profit"].where(df["operating_profit"] > 0)
    r["free_cash_flow_cr"] = df["cfo"] + df["cfi"]
    r["capex_cr"] = df["cfi"].abs()
    r["capex_intensity_pct"] = r["capex_cr"] / sales * 100
    r["cfo_to_pat"] = df["cfo"] / df["net_profit"].where(df["net_profit"] > 0)
    r["fcf_conversion_pct"] = r["free_cash_flow_cr"] / df["operating_profit"].where(df["operating_profit"] > 0) * 100
    r["earnings_per_share"] = df["eps"]
    r["book_value_per_share"] = eq / (df["equity_capital"] / df["face_value"].where(df["face_value"] > 0))
    r["dividend_payout_ratio_pct"] = df["dividend_payout"]
    r["total_debt_cr"] = df["borrowings"]
    r["cash_from_operations_cr"] = df["cfo"]
    r["sales_cr"] = df["sales"]
    r["net_profit_cr"] = df["net_profit"]
    r["operating_profit_cr"] = df["operating_profit"]

    # DQ-17: balance sheet on a different scale than the P&L -> BS-derived ratios are meaningless
    suspect = (df["sales"] / ta) > BS_SCALE_MAX_TURNOVER
    r["bs_scale_suspect"] = suspect.fillna(False).astype(int)
    r.loc[suspect.fillna(False), BS_DERIVED] = np.nan
    log += [f"{c} FY{f}: BS_SCALE_SUSPECT - balance-sheet ratios set to NULL" for c, f in zip(df.loc[suspect.fillna(False), "company_id"], df.loc[suspect.fillna(False), "fy"])]

    flags = pd.Series("", index=df.index)
    for n in (3, 5, 10):
        for col, short in (("sales", "revenue"), ("net_profit", "pat"), ("eps", "eps")):
            if short == "eps" and n != 5:
                continue
            v, f = _growth(df, col, n, f"{short}_cagr_{n}y", log)
            r[f"{short}_cagr_{n}y"] = v
            flags = flags.where(f == "", flags + f"{short}_{n}y:" + f + ";")
    v, f = _growth(r.assign(_fcf=r["free_cash_flow_cr"]), "_fcf", 5, "fcf_cagr_5y", log)
    r["fcf_cagr_5y"] = v
    flags = flags.where(f == "", flags + "fcf_5y:" + f + ";")
    r["cagr_flags"] = flags

    # FCF concern: negative FCF three consecutive years
    neg = (r["free_cash_flow_cr"] < 0).astype(int)
    r["fcf_concern"] = (neg.groupby(r["company_id"]).rolling(3).sum().reset_index(level=0, drop=True) == 3).astype(int)
    r["capital_allocation"] = [
        capital_pattern(a, b, c, d) for a, b, c, d in zip(df["cfo"], df["cfi"], df["cff"], df["dividend_payout"])
    ]
    # Banks/NBFCs/insurers book loan growth in operating cash flow, so CFO < 0 is structural, not distress
    neg_cfo = r["capital_allocation"].isin(["Distress Signal", "Cash Burn", "Asset Liquidation"]) & (r["is_financial"] == 1)
    r.loc[neg_cfo, "capital_allocation"] = "Lending Growth (Financials)"
    r["cfo_sign"], r["cfi_sign"], r["cff_sign"] = (np.sign(df[c]).fillna(0).astype(int) for c in ("cfo", "cfi", "cff"))
    r["is_latest"] = (r["fy"] == r.groupby("company_id")["fy"].transform("max")).astype(int)
    r = r.replace([np.inf, -np.inf], np.nan)
    return r.drop(columns=["broad_sector"]), log


def _winsor_scale(s: pd.Series, higher_better: bool = True) -> pd.Series:
    """Scale to 0-100 after winsorising at P10/P90."""
    lo, hi = s.quantile(0.10), s.quantile(0.90)
    if pd.isna(lo) or hi == lo:
        return pd.Series(50.0, index=s.index).where(s.notna())
    sc = ((s.clip(lo, hi) - lo) / (hi - lo)) * 100
    return sc if higher_better else 100 - sc


def add_quality_score(r: pd.DataFrame) -> pd.DataFrame:
    """Composite Quality Score = .30 ROE + .25 FCF conversion + .25 ROCE + .20 D/E (0-100, per fy x financial-flag group)."""
    parts = {}
    for key, col, hb in (("roe", "return_on_equity_pct", True), ("fcf", "fcf_conversion_pct", True),
                         ("roce", "roce_pct", True), ("de", "debt_to_equity", False)):
        parts[key] = r.groupby(["fy", "is_financial"])[col].transform(lambda s, hb=hb: _winsor_scale(s, hb))
    w = {"roe": .30, "fcf": .25, "roce": .25, "de": .20}
    avail = sum(parts[k].notna() * w[k] for k in w)
    n_parts = sum(parts[k].notna().astype(int) for k in w)
    score = sum(parts[k].fillna(0) * w[k] for k in w) / avail.replace(0, np.nan)
    r["composite_quality_score"] = score.where(n_parts >= 3).round(1)  # a score from 1-2 inputs is not meaningful
    return r


def build_ratios(db_path: Path = DB_PATH, out_dir: Path = ROOT / "output") -> pd.DataFrame:
    """Compute ratios, write `financial_ratios` table, capital_allocation.csv and ratio_edge_cases.log."""
    with sqlite3.connect(db_path) as conn:
        r, log = compute_ratios(_load(conn))
        r = add_quality_score(r)
        r.to_sql("financial_ratios", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS ix_fr ON financial_ratios(company_id, fy)")
    out_dir.mkdir(exist_ok=True)
    r[["company_id", "year", "cfo_sign", "cfi_sign", "cff_sign", "capital_allocation"]].rename(
        columns={"capital_allocation": "pattern_label"}).to_csv(out_dir / "capital_allocation.csv", index=False)
    (out_dir / "ratio_edge_cases.log").write_text("\n".join(log))
    logger.info("financial_ratios: %d rows, %d edge cases", len(r), len(log))
    return r


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    df = build_ratios()
    print(df.shape, df["is_latest"].sum())
