"""N100 Financial Intelligence Platform - Streamlit entry point. Run: streamlit run src/dashboard/app.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # project root, so `import src...` works under `streamlit run`

import streamlit as st

from src.dashboard.utils.db import page_setup, query

page_setup("N100 Financial Intelligence", "🏦")
st.markdown("Use the sidebar to open a screen: **Home**, **Company Profile**, **Screener**, **Peers**, **Trends**, "
            "**Sectors**, **Capital Allocation**, **Annual Reports**, **Valuation** and **Cash Flow**.")
c = query("SELECT (SELECT COUNT(*) FROM companies) n, (SELECT COUNT(*) FROM financial_ratios) r")
a, b = st.columns(2)
a.metric("Companies", int(c.n[0]))
b.metric("Company-year ratio rows", int(c.r[0]))
st.info("Start with **Home** for the universe overview, or **Company Profile** to drill into one ticker.")
