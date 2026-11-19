"""Peer Comparison: company vs peer-group average radar, side-by-side KPI table (benchmark highlighted), percentile ranks."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # project root, so `import src...` works under `streamlit run`

import pandas as pd
import streamlit as st

from src.analytics.peer import PEER_METRICS, RADAR_METRICS
from src.dashboard.utils.charts import radar
from src.dashboard.utils.db import get_peers, page_setup, query
from src.dashboard.utils.tables import heatmap_table, plain_table

page_setup("Peer Comparison", "👥")
groups = query("SELECT DISTINCT peer_group_name g FROM peer_groups ORDER BY 1")["g"].tolist()
grp = st.sidebar.selectbox("Peer group", groups)
years = query("SELECT DISTINCT fy FROM peer_percentiles WHERE peer_group=? ORDER BY fy DESC", (grp,))["fy"].tolist()
fy = st.sidebar.selectbox("Year", years)
members = get_peers(grp)
bench_id = members.loc[members["is_benchmark"] == 1, "company_id"].iloc[0] if (members["is_benchmark"] == 1).any() else None
pp = query("SELECT * FROM peer_percentiles WHERE peer_group=? AND fy=?", (grp, int(fy)))
ids = sorted(pp["company_id"].unique())
if not ids:
    st.info("No data for this peer group and year.")
    st.stop()
sel = st.sidebar.selectbox("Company on radar", ids, index=ids.index(bench_id) if bench_id in ids else 0)
st.caption(f"{len(members)} companies in the group · benchmark company: **{bench_id}**. Only companies with data for this year are shown.")

vals = pp.pivot(index="company_id", columns="metric", values="value").reindex(columns=list(PEER_METRICS)).astype(float)


def normalise(col: str) -> pd.Series:
    """0-100 within the group (100 = best; D/E inverted)."""
    v = vals[col]
    lo, hi = v.min(), v.max()
    n = pd.Series(50.0, index=v.index).where(v.notna()) if hi == lo else (v - lo) / (hi - lo) * 100
    return n if PEER_METRICS[col][1] else 100 - n


norm = pd.DataFrame({c: normalise(c) for c in RADAR_METRICS})
labels = [PEER_METRICS[m][0] for m in RADAR_METRICS]
series = {sel: norm.loc[sel].fillna(0).tolist(), "Peer group average": norm.mean().fillna(0).tolist()}
if bench_id in norm.index and bench_id != sel:
    series[f"Benchmark ({bench_id})"] = norm.loc[bench_id].fillna(0).tolist()
tab1, tab2, tab3 = st.tabs(["Radar & KPI table", "Percentile ranks", "Gap vs benchmark"])
with tab1:
    st.plotly_chart(radar(series, labels, f"{sel} vs {grp} peers (0-100 within group, 100 = best)"), width="stretch")
    st.subheader("Side-by-side KPIs")
    kpi = vals.copy()
    kpi.columns = [PEER_METRICS[c][0] for c in kpi.columns]
    text = plain_table(kpi)
    st.dataframe(text.style.apply(lambda row: ["background-color:#1F3864;color:#fff;font-weight:bold" if row.name == bench_id else "" for _ in row], axis=1), width="stretch")
    st.caption("Highlighted row = benchmark company.")
with tab2:
    wide = pp.pivot(index="company_id", columns="metric", values="percentile_rank")[list(PEER_METRICS)].astype(float)
    wide.columns = [PEER_METRICS[c][0] for c in wide.columns]
    st.dataframe(heatmap_table(wide * 100), width="stretch")
    fl = query("SELECT company_id, best_in_class, watch_list FROM peer_flags WHERE peer_group=? AND fy=?", (grp, int(fy)))
    a, b = st.columns(2)
    a.success("Best in Class: " + (", ".join(fl[fl.best_in_class == 1].company_id) or "none"))
    b.warning("Watch List: " + (", ".join(fl[fl.watch_list == 1].company_id) or "none"))
with tab3:
    if bench_id in vals.index:
        gap = vals - vals.loc[bench_id]
        gap.columns = [PEER_METRICS[c][0] for c in gap.columns]
        st.dataframe(plain_table(gap), width="stretch")
    else:
        st.info("Benchmark company has no data for this year.")
