"""Company Profile: search, company card, 6 KPI tiles, charts, pros & cons badges."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # project root, so `import src...` works under `streamlit run`

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.dashboard.utils.charts import bar_line, stacked
from src.dashboard.utils.db import company_picker, fmt, get_bs, get_cf, get_companies, get_pl, get_ratios, page_setup, query, table_exists
from src.dashboard.utils.logos import badge_svg, logo_for

page_setup("Company Profile", "🏢")
ids = set(get_companies()["id"])
wanted = (st.query_params.get("ticker") or "").strip().upper()          # deep link: /profile?ticker=TCS
if wanted and wanted not in ids:
    st.warning("Ticker not found — please try another")
elif wanted:
    st.session_state["ticker"] = wanted
t = company_picker("Search company name or ticker")
co = query("SELECT c.*, s.broad_sector, s.sub_sector FROM companies c LEFT JOIN sectors s ON s.company_id=c.id WHERE c.id=?", (t,))
if co.empty:
    st.warning("Ticker not found — please try another")
    st.stop()
co = co.iloc[0]

shared = query("SELECT COUNT(*) n FROM companies WHERE company_logo = ?", (co["company_logo"] or "",))["n"][0]
show_logo = st.sidebar.checkbox("Show logo", value=True)
l, r = st.columns([1, 4])
with l:
    if show_logo:
        try:
            st.image(logo_for(t, co["website"], co["company_logo"], shared == 1), width=110)
        except Exception:  # never let a logo break the page
            st.image(badge_svg(t), width=110)
with r:
    st.subheader(co["company_name"])
    st.caption(f"NSE: **{t}** · {co['broad_sector']} · {co['sub_sector']}")
    st.write(co["about_company"] or "")
    links = [f"[{n}]({co[c]})" for n, c in (("Website", "website"), ("NSE", "nse_profile"), ("BSE", "bse_profile"), ("Chart", "chart_link")) if co[c]]
    st.markdown(" · ".join(links))

rat = get_ratios(t)
if rat.empty:
    st.warning("No ratio data for this company.")
    st.stop()
lo, hi = int(rat.fy.min()), int(rat.fy.max())
yr = st.sidebar.slider("Year range", lo, hi, (lo, hi)) if hi > lo else (lo, hi)
if len(rat) < 10:
    st.info(f"Data available: {len(rat)} years (FY{lo}–FY{hi}). Long-window metrics are shown as N/A where history is too short.")
rat = rat[rat.fy.between(*yr)]
last = rat.iloc[-1]
k = st.columns(6)
for col, (lab, val, suf, nd) in zip(k, [("ROE", last.return_on_equity_pct, "%", 1), ("ROCE", last.roce_pct, "%", 1), ("Net profit margin", last.net_profit_margin_pct, "%", 1),
                                         ("D/E", last.debt_to_equity, "x", 2), ("Revenue CAGR 5Y", last.revenue_cagr_5y, "%", 1), ("FCF (latest, ₹ Cr)", last.free_cash_flow_cr, "", 0)]):
    col.metric(lab, fmt(val, suf, nd).replace("—", "N/A"))
st.caption(f"Composite quality score: **{fmt(last.composite_quality_score, '', 0).replace('—', 'N/A')}** / 100")
if last.is_financial:
    st.info("Financial company: ROCE and D/E are not meaningful for banks, NBFCs and insurers (deposits and float count as borrowings). Compare ROE, margins and growth instead.")
if last.cagr_flags:
    st.caption(f"CAGR flags: {last.cagr_flags}")

pl, bs, cf = get_pl(t), get_bs(t), get_cf(t)
pl, bs, cf = (d[d.fy.between(*yr)] for d in (pl, bs, cf))
a, b = st.columns(2)
a.plotly_chart(bar_line(pl, "year", ["sales", "net_profit"], "Revenue & net profit (₹ Cr)"), width="stretch")
if rat[["return_on_equity_pct", "roce_pct"]].isna().all().all():
    b.info("ROE / ROCE unavailable (no usable balance sheet in the source data).")
else:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=rat["year"], y=rat["return_on_equity_pct"], name="ROE %", mode="lines+markers"), secondary_y=False)
    fig.add_trace(go.Scatter(x=rat["year"], y=rat["roce_pct"], name="ROCE %", mode="lines+markers"), secondary_y=True)
    fig.update_yaxes(title_text="ROE %", secondary_y=False)
    fig.update_yaxes(title_text="ROCE %", secondary_y=True)
    fig.update_layout(title="ROE and ROCE (%)", height=330, margin=dict(t=40, b=10), legend=dict(orientation="h"))
    b.plotly_chart(fig, width="stretch")
c, d = st.columns(2)
if bs.empty:
    c.info("No balance sheet available for this company in the source data.")
else:
    c.plotly_chart(stacked(bs, "year", ["equity", "borrowings", "other_liabilities"], "Liabilities composition (₹ Cr)"), width="stretch")
d.plotly_chart(bar_line(cf, "year", ["operating_activity", "investing_activity", "financing_activity"], "Cash flow (₹ Cr)"), width="stretch")

if table_exists("pros_cons_generated"):
    gen = query("SELECT type, text, confidence_pct FROM pros_cons_generated WHERE company_id=? ORDER BY confidence_pct DESC", (t,))
else:
    gen = query("SELECT 'pro' AS type, '' AS text, 0.0 AS confidence_pct WHERE 0")
    st.info("Rule-based pros & cons are not generated yet. Run `python -m src.pipeline`, then restart the app.")
if not gen.empty:
    st.subheader("Pros & cons")
    p, c2 = st.columns(2)
    p.markdown("\n".join(f"- ✅ {r.text} *({r.confidence_pct:.0f}%)*" for r in gen[gen.type == "pro"].itertuples()))
    c2.markdown("\n".join(f"- ❌ {r.text} *({r.confidence_pct:.0f}%)*" for r in gen[gen.type == "con"].itertuples()))
    st.caption("Auto-generated from KPI threshold rules; percentage = rule confidence.")
src_pc = query("SELECT pros, cons FROM prosandcons WHERE company_id=?", (t,))
if not src_pc.empty:
    with st.expander("Source pros & cons (from Screener.in data)"):
        p, c2 = st.columns(2)
        p.markdown("\n".join(f"- ✅ {x}" for x in src_pc["pros"].dropna()))
        c2.markdown("\n".join(f"- ❌ {x}" for x in src_pc["cons"].dropna()))
pdf = Path(__file__).resolve().parents[3] / "reports" / "tearsheets" / f"{t.replace('&', '_').replace('/', '_')}_tearsheet.pdf"
if pdf.exists():
    st.download_button("⬇ Download tearsheet (PDF)", pdf.read_bytes(), pdf.name, "application/pdf")
