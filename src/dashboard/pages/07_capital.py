"""Capital Allocation Map: treemap of CFO/CFI/CFF patterns with company drill-down."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # project root, so `import src...` works under `streamlit run`

import plotly.express as px
import streamlit as st

from src.dashboard.utils.db import page_setup, query

page_setup("Capital Allocation Map", "🧭")
years = query("SELECT DISTINCT fy FROM financial_ratios ORDER BY fy")["fy"].tolist()
fy = st.sidebar.select_slider("Year", years, value=max(years))
df = query("""SELECT r.company_id, c.company_name, r.capital_allocation AS pattern, r.sales_cr
              FROM financial_ratios r JOIN companies c ON c.id=r.company_id WHERE r.fy=?""", (int(fy),))
cnt = df.groupby("pattern").size().reset_index(name="companies")
st.plotly_chart(px.treemap(df.assign(root="Nifty 100"), path=["root", "pattern", "company_id"], height=480), width="stretch")
pat = st.selectbox("Drill down: pattern", cnt.sort_values("companies", ascending=False)["pattern"].tolist())
sub = df[df.pattern == pat][["company_id", "company_name", "sales_cr"]]
st.write(f"**{len(sub)}** companies in *{pat}* in FY{fy}")
st.dataframe(sub, hide_index=True, width="stretch")
st.download_button("⬇ CSV", sub.to_csv(index=False), f"capital_{pat}_{fy}.csv", "text/csv")
st.caption("Distress Signal = CFO < 0 with CFF > 0 (or CFI > 0 with CFF > 0). (+,−,−) is split into Reinvestor / Shareholder Returns by dividend payout ≥ 40%.")
