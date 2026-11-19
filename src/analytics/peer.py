"""Peer comparison: within-group percentile ranks, best-in-class and weak-company flags."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
# metric column -> (label, higher_is_better)
PEER_METRICS = {
    "return_on_equity_pct": ("ROE", True), "roce_pct": ("ROCE", True),
    "net_profit_margin_pct": ("NPM", True), "operating_profit_margin_pct": ("OPM", True),
    "debt_to_equity": ("D/E", False), "interest_coverage": ("ICR", True),
    "fcf_conversion_pct": ("FCF Conv.", True), "revenue_cagr_5y": ("Rev CAGR 5Y", True),
    "pat_cagr_5y": ("PAT CAGR 5Y", True), "eps_cagr_5y": ("EPS CAGR 5Y", True),
}
RADAR_METRICS = ["return_on_equity_pct", "roce_pct", "net_profit_margin_pct", "debt_to_equity",
                 "fcf_conversion_pct", "pat_cagr_5y", "revenue_cagr_5y", "eps_cagr_5y"]


def percent_rank(values: pd.Series, higher_is_better: bool = True) -> pd.Series:
    """PERCENT_RANK in [0,1] oriented so 1 = best (inverted when lower is better)."""
    v = values if higher_is_better else -values
    n = v.notna().sum()
    if n < 2:
        return pd.Series(float("nan"), index=values.index)
    return (v.rank(method="min") - 1) / (n - 1)


def compute_peer_percentiles(ratios: pd.DataFrame, groups: pd.DataFrame) -> pd.DataFrame:
    """Long table: company_id, peer_group, metric, value, percentile_rank, fy."""
    rows = []
    m = groups.merge(ratios, on="company_id")
    for (grp, fy), g in m.groupby(["peer_group_name", "fy"]):
        for col, (_, hb) in PEER_METRICS.items():
            pr = percent_rank(g[col], hb)
            rows.append(pd.DataFrame({"company_id": g["company_id"], "peer_group": grp, "metric": col,
                                      "value": g[col], "percentile_rank": pr, "fy": fy}))
    return pd.concat(rows, ignore_index=True)


def peer_flags(pp: pd.DataFrame) -> pd.DataFrame:
    """Best-in-class (>=75th pct on >=6 metrics) and Watch List (<=25th pct on >=4 metrics) per company-fy."""
    g = pp.groupby(["company_id", "peer_group", "fy"])["percentile_rank"]
    out = pd.DataFrame({"top_q": g.apply(lambda s: (s >= 0.75).sum()), "bottom_q": g.apply(lambda s: (s <= 0.25).sum())}).reset_index()
    out["best_in_class"] = (out["top_q"] >= 6).astype(int)
    out["watch_list"] = (out["bottom_q"] >= 4).astype(int)
    return out


def build_peers(db_path: Path = ROOT / "data" / "nifty100.db") -> pd.DataFrame:
    """Write peer_percentiles and peer_flags tables."""
    with sqlite3.connect(db_path) as conn:
        ratios = pd.read_sql("SELECT * FROM financial_ratios", conn)
        groups = pd.read_sql("SELECT peer_group_name, company_id, is_benchmark FROM peer_groups", conn)
        pp = compute_peer_percentiles(ratios, groups)
        pp.to_sql("peer_percentiles", conn, if_exists="replace", index=False)
        peer_flags(pp).to_sql("peer_flags", conn, if_exists="replace", index=False)
    return pp


if __name__ == "__main__":
    print(build_peers().shape)
