"""Manual: Company Profile server-side render time for 5 tickers (spec: each < 3 s). Run: python tests/dashboard/measure_profile_load.py"""
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from streamlit.testing.v1 import AppTest  # noqa: E402

TICKERS = ["TCS", "HDFCBANK", "RELIANCE", "SUNPHARMA", "HINDUNILVR"]
print(f"{'ticker':12s} first load (cold cache)   repeat (cached)")
cold_all = []
for t in TICKERS:
    at = AppTest.from_file(str(ROOT / "src/dashboard/pages/02_profile.py"), default_timeout=60)
    at.session_state["ticker"] = t
    t0 = time.perf_counter(); at.run(); cold = time.perf_counter() - t0
    t0 = time.perf_counter(); at.run(); warm = time.perf_counter() - t0
    cold_all.append(cold)
    print(f"{t:12s} {cold:6.2f} s {'OK' if cold < 3 else 'SLOW':>5s}          {warm:6.2f} s")
print(f"max cold = {max(cold_all):.2f} s, median = {statistics.median(cold_all):.2f} s  (render time only: add browser paint ~0.3 s)")
