"""Config-driven investment screener, composite score and universe loader."""
from __future__ import annotations

import operator
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "screener_config.yaml"
OPS = {">=": operator.ge, "<=": operator.le}
MARKET_FY = 2024  # latest simulated valuation year


def load_config(path: Path = CONFIG) -> dict:
    """Read screener_config.yaml."""
    return yaml.safe_load(Path(path).read_text())


def load_universe(conn: sqlite3.Connection, fy: int | None = None) -> pd.DataFrame:
    """One row per company: latest (or given-fy) ratios + sector + simulated market multiples."""
    where = "r.is_latest = 1" if fy is None else f"r.fy = {int(fy)}"
    df = pd.read_sql(
        f"""SELECT r.*, c.company_name, s.sub_sector, s.market_cap_category,
                   m.market_cap_crore, m.enterprise_value_crore, m.pe_ratio, m.pb_ratio, m.ev_ebitda, m.dividend_yield_pct
            FROM financial_ratios r JOIN companies c ON c.id = r.company_id
            LEFT JOIN sectors s ON s.company_id = r.company_id
            LEFT JOIN market_cap m ON m.company_id = r.company_id AND m.year = MIN(r.fy, {MARKET_FY})
            WHERE {where}""", conn)
    prev = pd.read_sql("SELECT company_id, fy+1 AS fy, debt_to_equity AS de_prev FROM financial_ratios", conn)
    df = df.merge(prev, on=["company_id", "fy"], how="left")
    df["broad_sector"] = df["company_id"].map(
        pd.read_sql("SELECT company_id, broad_sector FROM sectors", conn).set_index("company_id")["broad_sector"])
    df["fcf_yield_pct"] = df["free_cash_flow_cr"] / df["market_cap_crore"] * 100
    return df


def apply_filters(df: pd.DataFrame, filters: dict, cfg: dict | None = None, carve_out: bool = True) -> pd.DataFrame:
    """Keep rows passing all filters. NaN fails a filter (unless null_passes); financials skip carve-out filters."""
    cfg = cfg or load_config()
    mask = pd.Series(True, index=df.index)
    for name, thr in filters.items():
        spec = cfg["filters"][name]
        col = df[spec["column"]]
        ok = OPS[spec["op"]](col, thr)
        if spec.get("null_passes"):
            ok = ok | col.isna()
        if carve_out and spec.get("skip_financials"):
            ok = ok | (df["is_financial"] == 1)
        mask &= ok.fillna(False)
    return df[mask]


def _scale(s: pd.Series) -> pd.Series:
    lo, hi = s.quantile(0.10), s.quantile(0.90)
    return pd.Series(50.0, index=s.index).where(s.notna()) if hi == lo else ((s.clip(lo, hi) - lo) / (hi - lo) * 100)


def _de_score(de: float) -> float:
    return np.nan if pd.isna(de) else float(np.interp(de, [0, 0.5, 1, 2, 5], [100, 85, 70, 50, 0]))


def _icr_score(icr: float) -> float:
    return 100.0 if pd.isna(icr) else float(np.interp(icr, [1.5, 3, 5, 10], [0, 50, 75, 100]))


def composite_score(df: pd.DataFrame, cfg: dict | None = None) -> pd.Series:
    """Composite score 0-100 per spec 25.1. TURNAROUND CAGR scores 0; financials get neutral leverage (50)."""
    cfg = cfg or load_config()
    d = df.copy()
    d["fcf_positive"] = np.where(d["free_cash_flow_cr"] > 0, 100.0, 0.0)
    d["de_score"] = d["debt_to_equity"].map(_de_score)
    d["icr_score"] = d["interest_coverage"].map(_icr_score)
    total = pd.Series(0.0, index=d.index)
    for dim in cfg["composite_weights"].values():
        for col, w in dim["parts"].items():
            if col in ("fcf_positive", "de_score", "icr_score"):
                s = d[col]
            else:
                s = _scale(d[col])
                if "cagr" in col:  # undefined CAGR (turnaround / loss) scores 0, not neutral
                    s = s.fillna(0)
            s = s.fillna(0)
            if col in ("de_score", "icr_score"):
                s = s.where(d["is_financial"] == 0, 50.0)
            total += s * dim["weight"] * (w / sum(dim["parts"].values()))
    return total.round(1)


def run_preset(df: pd.DataFrame, name: str, cfg: dict | None = None) -> pd.DataFrame:
    """Run one preset screener and return ranked rows."""
    cfg = cfg or load_config()
    p = cfg["presets"][name]
    d = df.copy()
    d["composite_score"] = composite_score(d, cfg)
    out = apply_filters(d, p["filters"], cfg, carve_out=not p.get("no_financial_carveout", False))
    if p.get("extra") == "de_declining":
        out = out[out["debt_to_equity"] < out["de_prev"]]
    return out.sort_values(p["rank_by"], ascending=False)
