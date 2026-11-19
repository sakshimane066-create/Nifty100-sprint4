"""Valuation (SIMULATED market data): multiples, flags, P/E trend, FCF yield."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # project root, so `import src...` works under `streamlit run`

import plotly.express as px
import streamlit as st

from src.dashboard.utils.db import get_conn, page_setup, query
from src.analytics.valuation import build_valuation

page_setup("Valuation (simulated data)", "💹")
st.warning("Market cap and multiples come from `market_cap.xlsx`, a **simulated** dataset. Method demonstration only.")
v = build_valuation(get_conn())
flt = st.sidebar.multiselect("Flag", ["Caution", "Discount", "Fair", "N/A"])
sec = st.sidebar.multiselect("Sector", sorted(v["broad_sector"].unique()))
view = v[(v["pe_flag"].isin(flt)) if flt else v.index.notna()]
view = view[view["broad_sector"].isin(sec)] if sec else view
cols = ["company_id", "company_name", "broad_sector", "pe_ratio", "sector_median_pe_ratio", "pe_flag", "pb_ratio", "ev_ebitda", "ev_ebitda_flag",
        "dividend_yield_pct", "fcf_yield_pct", "above_own_5y_pe"]
st.dataframe(view[cols].round(2), hide_index=True, width="stretch")
st.download_button("⬇ CSV", view[cols].to_csv(index=False), "valuation.csv", "text/csv")
t = st.selectbox("P/E trend for", v["company_id"].tolist())
h = query("SELECT year, pe_ratio, pb_ratio, ev_ebitda FROM market_cap WHERE company_id=? ORDER BY year", (t,))
st.plotly_chart(px.line(h, x="year", y=["pe_ratio", "pb_ratio", "ev_ebitda"], markers=True, height=360), width="stretch")
st.subheader("Top dividend yields")
st.dataframe(v.nsmallest(10, "dividend_yield_rank")[["company_id", "company_name", "dividend_yield_pct"]], hide_index=True)
