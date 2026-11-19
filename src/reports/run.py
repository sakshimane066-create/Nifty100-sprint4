"""Generate all reports: 92 tearsheets, one report per sector, the portfolio summary."""
from __future__ import annotations

import logging
import time
from pathlib import Path

from src.reports.common import ROOT, ReportData
from src.reports.portfolio_report import make_portfolio_report
from src.reports.sector_report import make_sector_report
from src.reports.tearsheet import make_tearsheet

logger = logging.getLogger(__name__)


def build_all(out_root: Path = ROOT / "reports", db_path: Path = ROOT / "data" / "nifty100.db") -> dict:
    """Write every report and return counts."""
    data = ReportData.load(db_path)
    t0 = time.time()
    tickers = data.tickers()
    for t in tickers:
        make_tearsheet(data, t, out_root / "tearsheets")
    sectors = sorted(data.sectors["broad_sector"].unique())
    for s in sectors:
        make_sector_report(data, s, out_root / "sector")
    portfolio = make_portfolio_report(data, out_root / "portfolio")
    return {"tearsheets": len(tickers), "sector_reports": len(sectors), "portfolio": portfolio.name, "seconds": round(time.time() - t0, 1)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(build_all())
