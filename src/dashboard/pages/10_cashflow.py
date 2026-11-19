"""Cash Flow Intelligence: earnings quality, CapEx intensity, FCF conversion, deleveraging and distress alerts."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # project root, so `import src...` works under `streamlit run`

import plotly.express as px
import streamlit as st

from src.dashboard.utils.db import page_setup, query, table_exists
from src.dashboard.utils.tables import to_excel_bytes

page_setup("Cash Flow Intelligence", "💧")
if not table_exists("cashflow_intelligence"):
    st.warning("Cash-flow intelligence has not been generated yet. Run `python -m src.pipeline` (or `python -m src.analytics.cashflow_intel`), then restart the app.")
    st.stop()
df = query("SELECT * FROM cashflow_intelligence ORDER BY broad_sector, company_id")
sectors = sorted(df["broad_sector"].unique())
sec = st.sidebar.multiselect("Sector", sectors)
qual = st.sidebar.multiselect("Earnings quality", ["High Quality Earnings", "Moderate", "Accrual Risk"])
only_distress = st.sidebar.checkbox("Distress signal only")
view = df[df["broad_sector"].isin(sec)] if sec else df
view = view[view["cfo_quality"].isin(qual)] if qual else view
view = view[view["distress_latest"] == 1] if only_distress else view
k = st.columns(4)
k[0].metric("Companies shown", len(view))
k[1].metric("High-quality earnings", int((view.cfo_quality == "High Quality Earnings").sum()))
k[2].metric("Accrual risk", int((view.cfo_quality == "Accrual Risk").sum()))
k[3].metric("Distress signal (latest yr)", int(view.distress_latest.sum()))
cols = ["company_id", "company_name", "broad_sector", "cfo_pat_5y", "cfo_quality", "capex_intensity_5y_pct", "capex_category", "fcf_cagr_5y",
        "fcf_cagr_5y_flag", "fcf_conversion_5y_pct", "fcf_conversion_tier", "deleveraging_years_5y", "distress_latest", "capital_allocation"]
st.dataframe(view[cols].round(2), hide_index=True, width="stretch")
a, b = st.columns(2)
a.download_button("⬇ CSV", view[cols].to_csv(index=False), "cashflow_intelligence.csv", "text/csv")
b.download_button("⬇ Excel", to_excel_bytes(view[cols].round(2), "Cash Flow"), "cashflow_intelligence.xlsx",
                  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
nf = view[view.is_financial == 0].dropna(subset=["cfo_pat_5y", "fcf_conversion_5y_pct"])
if not nf.empty:
    st.subheader("Earnings quality vs FCF conversion (non-financials)")
    st.plotly_chart(px.scatter(nf, x="cfo_pat_5y", y="fcf_conversion_5y_pct", color="broad_sector", hover_name="company_name",
                               labels={"cfo_pat_5y": "CFO / PAT (5Y)", "fcf_conversion_5y_pct": "FCF conversion % (5Y)"}, height=420), width="stretch")
st.caption("CapEx uses |investing cash flow| as a proxy and can include non-CapEx items. Banks, NBFCs and insurers are excluded from the tiers.")
