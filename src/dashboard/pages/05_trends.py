"""Trend Analysis: metric history, YoY change, multi-metric overlay."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # project root, so `import src...` works under `streamlit run`

import plotly.graph_objects as go
import streamlit as st

from src.dashboard.utils.db import company_picker, page_setup, query

page_setup("Trend Analysis", "📈")
METRICS = {
    "sales_cr": "Revenue (₹ Cr)", "net_profit_cr": "Net profit (₹ Cr)", "operating_profit_margin_pct": "OPM %",
    "net_profit_margin_pct": "Net margin %", "return_on_equity_pct": "ROE %", "roce_pct": "ROCE %",
    "debt_to_equity": "D/E", "free_cash_flow_cr": "Free cash flow (₹ Cr)", "earnings_per_share": "EPS (₹)",
    "asset_turnover": "Asset turnover", "composite_quality_score": "Quality score",
}
t = company_picker(sidebar=True)
sel = st.sidebar.multiselect("Metrics (overlay up to 3)", list(METRICS), default=["sales_cr"], max_selections=3, format_func=METRICS.get)
df = query("SELECT * FROM financial_ratios WHERE company_id=? ORDER BY fy", (t,))
if df.empty or not sel:
    st.info("Select a company and at least one metric.")
    st.stop()
fig = go.Figure()
for i, m in enumerate(sel):
    yoy_lbl = df[m].pct_change(fill_method=None).mul(100)
    labels = ["" if v != v else f"{v:+.1f}%" for v in yoy_lbl]       # YoY % change annotated on every data point
    fig.add_trace(go.Scatter(x=df["year"], y=df[m], mode="lines+markers+text", text=labels, textposition="top center", textfont=dict(size=9),
                             name=METRICS[m], yaxis="y" if i == 0 else f"y{i + 1}"))
fig.update_layout(height=460, legend=dict(orientation="h"), yaxis=dict(title=METRICS[sel[0]]),
                  **({"yaxis2": dict(overlaying="y", side="right", title=METRICS[sel[1]])} if len(sel) > 1 else {}),
                  **({"yaxis3": dict(overlaying="y", side="right", position=0.97, showgrid=False, title=METRICS[sel[2]])} if len(sel) > 2 else {}))
st.plotly_chart(fig, width="stretch")
yoy = df[["year"] + sel].set_index("year")
yoy_pct = yoy.pct_change(fill_method=None).mul(100).round(1).add_suffix(" YoY %")
st.dataframe(yoy.join(yoy_pct).round(2), width="stretch")
st.download_button("⬇ CSV", yoy.join(yoy_pct).to_csv(), f"{t}_trend.csv", "text/csv")
