"""Sector Analysis: bubble chart and sector median KPI comparison."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # project root, so `import src...` works under `streamlit run`

import plotly.express as px
import streamlit as st

from src.dashboard.utils.db import page_setup, query

page_setup("Sector Analysis", "🏭")
years = query("SELECT DISTINCT fy FROM financial_ratios WHERE fy>=2019 ORDER BY fy DESC")["fy"].tolist()
fy = st.sidebar.select_slider("Year", sorted(years), value=max(years))
metric = st.sidebar.selectbox("Median KPI", ["return_on_equity_pct", "roce_pct", "net_profit_margin_pct", "operating_profit_margin_pct",
                                              "debt_to_equity", "revenue_cagr_5y", "pat_cagr_5y", "composite_quality_score"])
df = query("""SELECT r.*, c.company_name, s.broad_sector, s.sub_sector, m.market_cap_crore FROM financial_ratios r
              JOIN companies c ON c.id=r.company_id JOIN sectors s ON s.company_id=r.company_id
              LEFT JOIN market_cap m ON m.company_id=r.company_id AND m.year=r.fy WHERE r.fy=?""", (int(fy),))
sectors = ["All"] + sorted(df["broad_sector"].dropna().unique())
sec = st.sidebar.selectbox("Sector", sectors)
view = df if sec == "All" else df[df["broad_sector"] == sec]
st.subheader("Revenue vs ROE (bubble = simulated market cap)")
b = view.dropna(subset=["sales_cr", "return_on_equity_pct"])
b = b[b["sales_cr"] > 0]
st.plotly_chart(px.scatter(b, x="sales_cr", y="return_on_equity_pct", size=b["market_cap_crore"].fillna(b["market_cap_crore"].median()),
                           color="sub_sector", hover_name="company_name", log_x=True, size_max=45, height=460,
                           labels={"sales_cr": "Revenue (₹ Cr, log)", "return_on_equity_pct": "ROE %"}), width="stretch")
med = df.groupby("broad_sector")[metric].median().sort_values(ascending=False).reset_index()
st.subheader(f"Sector median: {metric}")
st.plotly_chart(px.bar(med, x="broad_sector", y=metric, height=360), width="stretch")
st.caption("Financials structurally have high D/E and distorted OPM - compare them within the sector, not against others.")
st.dataframe(view[["company_id", "company_name", "sales_cr", "return_on_equity_pct", "roce_pct", "debt_to_equity", "composite_quality_score"]].round(1),
             hide_index=True, width="stretch")
