import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def conn():
    """Read-only connection to the built DB (build with `make load ratios peers`)."""
    db = ROOT / "data" / "nifty100.db"
    from src.pipeline import missing_tables

    gaps = missing_tables(db)
    if gaps:
        pytest.fail(f"Database is missing tables {gaps}. Run:  python -m src.pipeline   (the ETL step wipes derived tables), then re-run pytest.", pytrace=False)
    c = sqlite3.connect(db)
    yield c
    c.close()
