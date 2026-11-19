"""Home / Overview: 6 summary KPI tiles, sector donut, top-5 quality table, year selector."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # project root, so `import src...` works under `streamlit run`

import streamlit as st

from src.dashboard.utils.charts import donut
from src.dashboard.utils.db import fmt, page_setup, query

page_setup("Home / Overview", "🏠")
years = query("SELECT DISTINCT fy FROM financial_ratios WHERE fy BETWEEN 2019 AND 2024 ORDER BY fy DESC")["fy"].tolist()
fy = st.sidebar.selectbox("Fiscal year", years, index=0)
df = query(
    """SELECT r.*, c.company_name, s.broad_sector FROM financial_ratios r
       JOIN companies c ON c.id=r.company_id JOIN sectors s ON s.company_id=r.company_id WHERE r.fy=?""", (int(fy),))
pe = query("SELECT pe_ratio FROM market_cap WHERE year=?", (int(fy),))
sectors = sorted(df["broad_sector"].dropna().unique())
chosen = st.sidebar.multiselect("Sector filter", sectors, default=sectors)
df = df[df["broad_sector"].isin(chosen)]
debt_free = int(((df["is_financial"] == 0) & (df["debt_to_equity"] <= 0.05)).sum())  # D/E <= 0.05, non-financials
k = st.columns(6)
k[0].metric("Average ROE", fmt(df["return_on_equity_pct"].mean(), "%"))
k[1].metric("Median P/E (sim.)", fmt(pe["pe_ratio"].median(), "x"))
k[2].metric("Median D/E", fmt(df["debt_to_equity"].median(), "x", 2))
k[3].metric("Total companies", len(df))
k[4].metric("Median revenue CAGR 5Y", fmt(df["revenue_cagr_5y"].median(), "%"))
k[5].metric("Debt-free companies", debt_free)
st.caption(f"Median ROE: {fmt(df['return_on_equity_pct'].median(), '%')} · Average quality score: {fmt(df['composite_quality_score'].mean(), '', 0)} · "
           "companies with an unusable balance sheet (data issue) are excluded from ROE / D/E statistics.")
share = (df["composite_quality_score"] >= 70).mean() * 100 if len(df) else 0
st.success(f"Market health: {share:.0f}% of selected companies score ≥70 on the Composite Quality Score.")
l, r = st.columns(2)
l.plotly_chart(donut(df.groupby("broad_sector").size().reset_index(name="companies"), "broad_sector", "companies",
                     f"Companies by sector ({df['broad_sector'].nunique()} sectors in the data)"), width="stretch")
top = df.nlargest(5, "composite_quality_score")[["company_id", "company_name", "broad_sector", "composite_quality_score", "return_on_equity_pct", "roce_pct"]]
r.subheader("Top 5 by Composite Quality Score")
r.dataframe(top.round(1), hide_index=True, width="stretch")
