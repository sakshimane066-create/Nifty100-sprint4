"""Rule-based pros/cons generator: 12 pro rules + 12 con rules on KPI thresholds, plus sector-relative fallbacks."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

MIN_CONF = 61.0   # every emitted entry has confidence > 60 (deliverable D-14)
MAX_PER_SIDE = 5


@dataclass(frozen=True)
class Rule:
    """One threshold rule: `test` returns a strength in (0, 1] when triggered, else None."""
    rule_id: str
    kind: str                                   # "pro" | "con"
    test: Callable[[pd.Series], float | None]
    text: Callable[[pd.Series], str]
    non_financial_only: bool = False


def _s(x: float, lo: float, hi: float) -> float:
    """Strength 0.03..1 of x moving from lo (threshold) to hi (very strong)."""
    return float(np.clip((x - lo) / (hi - lo), 0.03, 1.0))


def _ok(*vals) -> bool:
    return all(v is not None and not pd.isna(v) for v in vals)


PRO_RULES = [
    Rule("P01_ROE_TRACK_RECORD", "pro", lambda f: _s(f.roe3, 20, 40) if _ok(f.roe3) and f.roe3 > 20 and f.roe3_min > 15 else None,
         lambda f: f"Company has a good return on equity (ROE) track record: 3 Years ROE {f.roe3:.1f}%"),
    Rule("P02_HIGH_ROCE", "pro", lambda f: _s(f.roce_pct, 25, 50) if _ok(f.roce_pct) and f.roce_pct > 25 else None,
         lambda f: f"Company has a healthy return on capital employed (ROCE) of {f.roce_pct:.1f}%", True),
    Rule("P03_DEBT_FREE", "pro", lambda f: 0.9 if _ok(f.debt_to_equity) and f.debt_to_equity < 0.05 else None,
         lambda f: "Company is almost debt free.", True),
    Rule("P04_REVENUE_GROWTH", "pro", lambda f: _s(f.revenue_cagr_5y, 15, 30) if _ok(f.revenue_cagr_5y) and f.revenue_cagr_5y > 15 else None,
         lambda f: f"Company has delivered good sales growth of {f.revenue_cagr_5y:.1f}% CAGR over last 5 years"),
    Rule("P05_PROFIT_GROWTH", "pro", lambda f: _s(f.pat_cagr_5y, 20, 40) if _ok(f.pat_cagr_5y) and f.pat_cagr_5y > 20 else None,
         lambda f: f"Company has delivered good profit growth of {f.pat_cagr_5y:.1f}% CAGR over last 5 years"),
    Rule("P06_FCF_POSITIVE_5Y", "pro", lambda f: 0.7 if f.fcf_pos_5y == 1 else None,
         lambda f: "Company has generated positive free cash flow in each of the last 5 years", True),
    Rule("P07_CASH_BACKED_EARNINGS", "pro", lambda f: _s(f.cfo_pat_5y, 1.0, 1.6) if _ok(f.cfo_pat_5y) and f.cfo_pat_5y > 1.0 else None,
         lambda f: f"Earnings are backed by cash: operating cash flow is {f.cfo_pat_5y:.2f}x profit over 5 years", True),
    Rule("P08_HIGH_MARGIN", "pro", lambda f: _s(f.net_profit_margin_pct, 20, 35) if _ok(f.net_profit_margin_pct) and f.net_profit_margin_pct > 20 else None,
         lambda f: f"Company has a high net profit margin of {f.net_profit_margin_pct:.1f}%", True),
    Rule("P09_HEALTHY_PAYOUT", "pro", lambda f: 0.6 if _ok(f.payout3) and 30 <= f.payout3 <= 70 else None,
         lambda f: f"Company has been maintaining a healthy dividend payout of {f.payout3:.1f}%"),
    Rule("P10_STRONG_INTEREST_COVER", "pro", lambda f: _s(f.interest_coverage, 10, 30) if _ok(f.interest_coverage) and f.interest_coverage > 10 else None,
         lambda f: f"Company comfortably services its debt: interest coverage of {f.interest_coverage:.1f}x", True),
    Rule("P11_MARGIN_EXPANSION", "pro", lambda f: _s(f.opm_change_3y, 2, 8) if _ok(f.opm_change_3y) and f.opm_change_3y > 2 else None,
         lambda f: f"Operating margin has expanded by {f.opm_change_3y:.1f} points over the last 3 years", True),
    Rule("P12_CONSISTENT_GROWTH", "pro", lambda f: 0.65 if f.rev_up_5y == 1 else None,
         lambda f: "Company has grown sales in each of the last 5 years"),
]
CON_RULES = [
    Rule("C01_LOW_ROE", "con", lambda f: _s(10 - f.roe3, 0, 10) if _ok(f.roe3) and f.roe3 < 10 else None,
         lambda f: f"Company has a low return on equity of {f.roe3:.1f}% over last 3 years"),
    Rule("C02_HIGH_LEVERAGE", "con", lambda f: _s(f.debt_to_equity, 2, 6) if _ok(f.debt_to_equity) and f.debt_to_equity > 2 else None,
         lambda f: f"Company has a high debt to equity ratio of {f.debt_to_equity:.1f}x", True),
    Rule("C03_LOW_INTEREST_COVER", "con", lambda f: _s(3 - f.interest_coverage, 0, 2.5) if _ok(f.interest_coverage) and f.interest_coverage < 3 else None,
         lambda f: f"Company has a low interest coverage ratio of {f.interest_coverage:.1f}x", True),
    Rule("C04_NEGATIVE_FCF_3Y", "con", lambda f: 0.8 if f.fcf_concern == 1 else None,
         lambda f: "Free cash flow has been negative for 3 years in a row", True),
    Rule("C05_WEAK_CASH_CONVERSION", "con", lambda f: _s(0.5 - f.cfo_pat_5y, 0, 0.5) if _ok(f.cfo_pat_5y) and f.cfo_pat_5y < 0.5 else None,
         lambda f: f"Cash conversion is weak: operating cash flow is only {f.cfo_pat_5y:.2f}x profit over 5 years", True),
    Rule("C06_POOR_SALES_GROWTH", "con", lambda f: _s(5 - f.revenue_cagr_5y, 0, 10) if _ok(f.revenue_cagr_5y) and f.revenue_cagr_5y < 5 else None,
         lambda f: f"The company has delivered a poor sales growth of {f.revenue_cagr_5y:.1f}% over past five years."),
    Rule("C07_PROFIT_DECLINE", "con", lambda f: 0.85 if f.net_profit_cr is not None and _ok(f.net_profit_cr) and f.net_profit_cr < 0
         else (_s(-f.pat_cagr_5y, 0, 15) if _ok(f.pat_cagr_5y) and f.pat_cagr_5y < 0 else None),
         lambda f: ("Company reported a net loss in the latest year" if _ok(f.net_profit_cr) and f.net_profit_cr < 0
                    else f"Profit has declined at {f.pat_cagr_5y:.1f}% CAGR over the last 5 years")),
    Rule("C08_LOW_MARGIN", "con", lambda f: _s(5 - f.net_profit_margin_pct, 0, 5) if _ok(f.net_profit_margin_pct) and 0 <= f.net_profit_margin_pct < 5 else None,
         lambda f: f"Company has a low net profit margin of {f.net_profit_margin_pct:.1f}%", True),
    Rule("C09_LOW_PAYOUT", "con", lambda f: 0.5 if _ok(f.payout3, f.net_profit_cr) and f.payout3 < 15 and f.net_profit_cr > 0 else None,
         lambda f: f"Dividend payout has been low at {f.payout3:.1f}% of profits over last 3 years"),
    Rule("C10_PAYOUT_EXCEEDS_PROFIT", "con", lambda f: 0.75 if _ok(f.payout_latest) and f.payout_latest > 100 else None,
         lambda f: f"Dividend payout of {f.payout_latest:.0f}% exceeds the profit earned"),
    Rule("C11_DISTRESS_PATTERN", "con", lambda f: 0.9 if f.capital_allocation == "Distress Signal" else None,
         lambda f: "Operating cash flow is negative and operations are being funded through financing (distress pattern)", True),
    Rule("C12_OTHER_INCOME_DEPENDENCE", "con", lambda f: _s(f.other_income_share, 40, 100) if _ok(f.other_income_share) and f.other_income_share > 40 else None,
         lambda f: f"Earnings depend on other income: {f.other_income_share:.0f}% of pre-tax profit", True),
]
RULES = PRO_RULES + CON_RULES
REL_METRICS = {"return_on_equity_pct": ("return on equity", True), "net_profit_margin_pct": ("net profit margin", True),
               "revenue_cagr_5y": ("5-year sales growth", True), "pat_cagr_5y": ("5-year profit growth", True),
               "roce_pct": ("return on capital employed", True), "debt_to_equity": ("leverage (D/E)", False)}


def build_features(conn: sqlite3.Connection) -> pd.DataFrame:
    """One feature row per company, from the ratio history (latest year + trailing windows)."""
    r = pd.read_sql("SELECT * FROM financial_ratios ORDER BY company_id, fy", conn)
    pl = pd.read_sql("SELECT company_id, fy, other_income, profit_before_tax FROM profitandloss", conn)
    r = r.merge(pl, on=["company_id", "fy"], how="left")
    rows = []
    for cid, g in r.groupby("company_id"):
        g = g.sort_values("fy")
        last = g.iloc[-1]
        roe_tail = g["return_on_equity_pct"].dropna().tail(3)
        cfo5, pat5 = g["cash_from_operations_cr"].tail(5), g["net_profit_cr"].tail(5)
        fcf5 = g["free_cash_flow_cr"].tail(5)
        sales5 = g["sales_cr"].tail(6)
        yoy = sales5.pct_change().dropna()
        opm = g["operating_profit_margin_pct"].dropna()
        pbt = last["profit_before_tax"]
        rows.append(dict(
            company_id=cid, is_financial=int(last["is_financial"]), years=len(g),
            roe3=roe_tail.mean() if len(roe_tail) >= 2 else np.nan, roe3_min=roe_tail.min() if len(roe_tail) >= 2 else np.nan,
            fcf_pos_5y=int(len(fcf5.dropna()) == 5 and (fcf5 > 0).all()),
            cfo_pat_5y=(cfo5.sum() / pat5.sum()) if cfo5.notna().sum() >= 4 and pat5.sum() > 0 else np.nan,
            payout3=g["dividend_payout_ratio_pct"].tail(3).mean(), payout_latest=last["dividend_payout_ratio_pct"],
            opm_change_3y=(opm.iloc[-1] - opm.iloc[-4]) if len(opm) >= 4 else np.nan,
            rev_up_5y=int(len(yoy) >= 5 and (yoy.tail(5) > 0).all()),
            other_income_share=(last["other_income"] / pbt * 100) if _ok(pbt, last["other_income"]) and pbt > 0 else np.nan,
            **{c: last[c] for c in ["roce_pct", "debt_to_equity", "revenue_cagr_5y", "pat_cagr_5y", "net_profit_margin_pct", "interest_coverage",
                                    "fcf_concern", "capital_allocation", "net_profit_cr", "return_on_equity_pct"]}))
    return pd.DataFrame(rows)


def _relative(df: pd.DataFrame, sectors: pd.Series) -> pd.DataFrame:
    """Within-sector percentile (1 = best) for the relative metrics."""
    out = df[["company_id"]].copy()
    out["sector"] = out["company_id"].map(sectors)
    for col, (_, hb) in REL_METRICS.items():
        v = df[col] if hb else -df[col]
        out[col] = v.groupby(out["sector"]).rank(pct=True)
    return out


def generate(features: pd.DataFrame, sectors: pd.Series) -> pd.DataFrame:
    """Return long table: company_id, type, rule_triggered, text, confidence_pct."""
    rel = _relative(features, sectors).set_index("company_id")
    out = []
    for _, f in features.iterrows():
        entries: dict[str, list] = {"pro": [], "con": []}
        for rule in RULES:
            if rule.non_financial_only and f.is_financial:
                continue
            try:
                s = rule.test(f)
            except Exception:  # missing input -> rule does not fire
                s = None
            if s is not None:
                entries[rule.kind].append((rule.rule_id, rule.text(f), round(60 + 35 * s, 1)))
        for kind in ("pro", "con"):
            entries[kind] = sorted(entries[kind], key=lambda e: -e[2])[:MAX_PER_SIDE]
        r = rel.loc[f.company_id, list(REL_METRICS)].dropna()
        if not entries["pro"] and len(r) and r.max() > 0.5:
            m, pct = r.idxmax(), r.max()
            entries["pro"].append(("R01_SECTOR_STRENGTH", f"Above the sector median on {REL_METRICS[m][0]} (sector percentile {pct * 100:.0f})",
                                   round(MIN_CONF + 20 * (pct - 0.5), 1)))
        if not entries["con"] and len(r) and r.min() < 0.5:
            m, pct = r.idxmin(), r.min()
            entries["con"].append(("R02_SECTOR_WEAKNESS", f"Below the sector median on {REL_METRICS[m][0]} (sector percentile {pct * 100:.0f})",
                                   round(MIN_CONF + 20 * (0.5 - pct), 1)))
        if not entries["pro"]:
            entries["pro"].append(("R03_GENERIC", "Company is a constituent of the Nifty 100 index", MIN_CONF))
        if not entries["con"]:
            n_missing = int(f[["roce_pct", "debt_to_equity", "return_on_equity_pct"]].isna().sum())
            entries["con"].append(("R04_DATA_GAP", f"{n_missing} balance-sheet-based ratios are unavailable, which limits the analysis" if n_missing
                                   else "No significant weakness identified; monitor valuation", MIN_CONF))
        for kind, lst in entries.items():
            for rid, text, conf in lst:
                out.append(dict(company_id=f.company_id, type=kind, rule_triggered=rid, text=text, confidence_pct=max(conf, MIN_CONF)))
    return pd.DataFrame(out)
