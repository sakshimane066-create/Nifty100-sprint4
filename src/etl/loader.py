"""ETL: read the 12 Excel files, normalise, validate, and load nifty100.db."""
from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path

import pandas as pd

from src.etl import validator as v
from src.etl.repair import apply_overrides, repair_swapped_ops
from src.etl.normaliser import PARSE_ERROR, TTM, fiscal_year, normalize_ticker, normalize_year, period_months

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
RAW, SUPPORT = ROOT / "data" / "raw", ROOT / "data" / "supporting"
CORE = ["companies", "profitandloss", "balancesheet", "cashflow", "analysis", "documents", "prosandcons"]
SUPPLEMENTARY = ["sectors", "stock_prices", "market_cap", "financial_ratios", "peer_groups"]
TS_TABLES = {"profitandloss": "profitandloss", "balancesheet": "balancesheet", "cashflow": "cashflow"}


def read_excel(name: str, base: Path | None = None) -> pd.DataFrame:
    """Read one source file. Core files carry a banner row (header=1); supplementary use header=0."""
    path = (base or (RAW if name in CORE else SUPPORT)) / f"{name}.xlsx"
    df = pd.read_excel(path, header=1 if name in CORE else 0)
    df.columns = [str(c).strip() for c in df.columns]
    if "company_id" in df.columns:
        df["company_id"] = df["company_id"].map(normalize_ticker)
    return df


def _clean_text(df: pd.DataFrame) -> pd.DataFrame:
    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].map(lambda x: x.replace("\n", " ").strip() if isinstance(x, str) else x)
    return df


def _add_year_cols(df: pd.DataFrame, with_period: bool = False) -> pd.DataFrame:
    raw = df["year"]
    df = df.copy()
    df["year"] = raw.map(normalize_year)
    df["fy"] = df["year"].map(fiscal_year)
    if with_period:
        df["period_months"] = raw.map(period_months)
    return df


def _audit(rows: list, table: str, n_in: int, n_out: int, t0: float) -> None:
    rows.append(dict(table=table, rows_in=n_in, rows_out=n_out, rejected=n_in - n_out,
                     timestamp=pd.Timestamp.now().isoformat(timespec="seconds"),
                     runtime_s=round(time.time() - t0, 3)))


def build_database(db_path: Path, out_dir: Path, check_urls: bool = False) -> dict:
    """Run the full ETL and return a summary dict. Idempotent: the DB is rebuilt each run."""
    out_dir.mkdir(parents=True, exist_ok=True)
    fails: list[dict] = []
    audit: list[dict] = []
    data = {n: _clean_text(read_excel(n)) for n in CORE + SUPPLEMENTARY}

    comp = data["companies"]
    t0 = time.time()
    comp["id"] = comp["id"].map(normalize_ticker)
    fails += v.dq01_company_pk(comp)
    if any(f["rule_id"] == "DQ-01" for f in fails):
        raise ValueError("DQ-01 CRITICAL: duplicate company ids; load halted")
    fails += v.dq08_ticker_format(comp.rename(columns={"id": "company_id"}), "companies")
    valid_ids = set(comp["id"].map(normalize_ticker))
    _audit(audit, "companies", len(comp), len(comp), t0)

    # ---- time series tables
    clean: dict[str, pd.DataFrame] = {}
    for name in TS_TABLES:
        t0 = time.time()
        df = _add_year_cols(data[name], with_period=(name == "profitandloss"))
        n_in = len(df)
        if name == "profitandloss":  # TTM rows are not annual periods; route them to their own table
            ttm = df[df["year"] == TTM].copy()
            df = df[df["year"] != TTM]
            clean["profitandloss_ttm"] = ttm[ttm["company_id"].isin(valid_ids)].drop(
                columns=["id", "year", "fy", "period_months"]).drop_duplicates("company_id", keep="last")
        fails += v.dq07_year_format(df, name)
        df = df[df["year"] != PARSE_ERROR]
        fails += v.dq08_ticker_format(df, name)
        fails += v.dq03_fk(df, name, valid_ids)
        df = df[df["company_id"].isin(valid_ids)]
        fails += v.dq02_annual_pk(df, name)
        df = df.drop_duplicates(["company_id", "year"], keep="last")
        clean[name] = df.drop(columns=["id"])
        _audit(audit, name, n_in, len(df), t0)

    pl, bs, cf = clean["profitandloss"], clean["balancesheet"], clean["cashflow"]
    fails += v.dq04_bs_balance(bs) + v.dq10_fixed_assets(bs) + v.dq15_strict_balance(bs)
    bs.loc[bs["fixed_assets"] < 0, "fixed_assets"] = 0
    pl, swapped = repair_swapped_ops(pl)
    clean["profitandloss"] = pl
    fails += v.dq18_swapped_ops(swapped)
    fails += v.dq05_opm(pl) + v.dq06_positive_sales(pl) + v.dq11_tax_range(pl)
    fails += v.dq12_payout_cap(pl) + v.dq14_eps_sign(pl)
    fails += v.dq09_net_cash(cf)
    mism = (cf["net_cash_flow"] - cf[["operating_activity", "investing_activity", "financing_activity"]].sum(axis=1)).abs() > 10
    cf.loc[mism, "net_cash_flow"] = cf.loc[mism, ["operating_activity", "investing_activity", "financing_activity"]].sum(axis=1)
    fails += v.dq16_coverage(pl, bs, cf)
    fails += v.dq17_bs_scale(pl, bs)

    # ---- other tables
    docs = data["documents"].rename(columns={"Year": "year", "Annual_Report": "annual_report"})
    n_in = len(docs)
    fails += v.dq03_fk(docs, "documents", valid_ids)
    docs = docs[docs["company_id"].isin(valid_ids)]
    if check_urls:
        fails += v.dq13_url(docs, _head_status(docs["annual_report"].dropna().unique()))
    clean["documents"] = docs
    _audit(audit, "documents", n_in, len(docs), time.time())

    comp, data["sectors"], ovr_log = apply_overrides(comp, data["sectors"])
    fails += v.dq19_overrides(ovr_log)
    for name in ["analysis", "prosandcons", "sectors", "stock_prices", "market_cap", "peer_groups"]:
        t0, df = time.time(), data[name]
        n_in = len(df)
        fails += v.dq03_fk(df, name, valid_ids)
        df = df[df["company_id"].isin(valid_ids)]
        if name == "sectors":
            df = df.drop(columns=["id"])
        if name in ("stock_prices", "market_cap", "peer_groups"):
            df = df.drop(columns=["id"])
        if name == "peer_groups":
            df["is_benchmark"] = df["is_benchmark"].astype(bool).astype(int)
        clean[name] = df
        _audit(audit, name, n_in, len(df), t0)

    t0, fr = time.time(), data["financial_ratios"]
    n_in = len(fr)
    fr = _add_year_cols(fr).drop(columns=["id"])
    fr = fr[fr["company_id"].isin(valid_ids) & (fr["year"] != PARSE_ERROR)].drop_duplicates(["company_id", "year"], keep="last")
    clean["financial_ratios_source"] = fr
    _audit(audit, "financial_ratios_source", n_in, len(fr), t0)
    clean["companies"] = comp

    # ---- write SQLite
    if db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    schema = (Path(__file__).parent / "schema.sql").read_text()
    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema)
        for table in ["companies"] + [t for t in clean if t != "companies"]:
            df = clean[table]
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
            df = df.rename(columns={c: c.lower() for c in df.columns})
            df[[c for c in cols if c in df.columns]].to_sql(table, conn, if_exists="append", index=False)
        bad = conn.execute("PRAGMA foreign_key_check").fetchall()
        if bad:
            raise RuntimeError(f"foreign_key_check failed: {len(bad)} rows")
    pd.DataFrame(audit).to_csv(out_dir / "load_audit.csv", index=False)
    vf = v.to_frame(fails)
    vf.to_csv(out_dir / "validation_failures.csv", index=False)
    logger.info("loaded %s tables; %d DQ records", len(clean), len(vf))
    return {"tables": {k: len(x) for k, x in clean.items()}, "dq": vf.groupby(["rule_id", "severity"]).size().to_dict()}


def _head_status(urls) -> dict[str, int]:
    """HEAD-request each URL (opt-in; needs network)."""
    import requests

    out = {}
    for u in urls:
        try:
            out[u] = requests.head(u, timeout=5, allow_redirects=True).status_code
        except requests.RequestException:
            out[u] = 0
    return out


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Build nifty100.db from the 12 Excel files")
    ap.add_argument("--check-urls", action="store_true", help="HEAD-check annual-report URLs (DQ-13, needs network)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    print(build_database(ROOT / "data" / "nifty100.db", ROOT / "output", check_urls=args.check_urls))
