"""One command that rebuilds everything in the right order:  python -m src.pipeline  [--reports]

The ETL step deletes and recreates data/nifty100.db, which drops every derived table, so all later steps must re-run.
"""
from __future__ import annotations

import argparse
import sqlite3
import time
from pathlib import Path

from src.analytics import cashflow_intel, peer, ratios, valuation
from src.etl import loader
from src.nlp import run as nlp_run

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "nifty100.db"
REQUIRED_TABLES = ["companies", "sectors", "profitandloss", "balancesheet", "cashflow", "financial_ratios", "peer_percentiles", "peer_flags",
                   "pros_cons_generated", "cashflow_intelligence"]


def missing_tables(db_path: Path = DB) -> list[str]:
    """Required tables that are not in the database (all of them if the file does not exist)."""
    if not db_path.exists():
        return list(REQUIRED_TABLES)
    with sqlite3.connect(db_path) as c:
        have = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return [t for t in REQUIRED_TABLES if t not in have]


def run_all(reports: bool = False) -> None:
    """ETL -> ratios -> peers -> valuation -> NLP -> cash-flow intelligence (-> PDF reports)."""
    steps = [
        ("ETL (12 Excel files -> SQLite)", lambda: loader.build_database(DB, ROOT / "output")),
        ("Ratio engine", lambda: ratios.build_ratios(DB, ROOT / "output")),
        ("Peer percentiles", lambda: peer.build_peers(DB)),
        ("Valuation", lambda: _valuation()),
        ("NLP: pros/cons, parser, tagger", lambda: nlp_run.build_nlp(DB, ROOT / "output")),
        ("Cash-flow intelligence", lambda: cashflow_intel.build_cashflow_intelligence(DB, ROOT / "output")),
    ]
    if reports:
        from src.reports.run import build_all

        steps.append(("PDF reports (takes ~1-2 min)", lambda: build_all(ROOT / "reports", DB)))
    for i, (name, fn) in enumerate(steps, 1):
        t0 = time.time()
        print(f"[{i}/{len(steps)}] {name} ...", flush=True)
        fn()
        print(f"      done in {time.time() - t0:.1f}s", flush=True)
    gaps = missing_tables()
    if gaps:
        raise SystemExit(f"Pipeline finished but these tables are missing: {gaps}")
    print("\nAll tables present. Next: python -m pytest   then   streamlit run src/dashboard/app.py")


def _valuation() -> None:
    with sqlite3.connect(DB) as conn:
        valuation.export_valuation(valuation.build_valuation(conn), ROOT / "output")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Rebuild the whole platform from the 12 Excel files")
    ap.add_argument("--reports", action="store_true", help="also regenerate the PDF reports (not needed for the dashboard)")
    run_all(ap.parse_args().reports)
