"""Financial Screener: 10 sliders, 6 preset buttons that fill the sliders, live results, CSV / Excel download."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # project root, so `import src...` works under `streamlit run`

import streamlit as st

from src.dashboard.utils.db import get_conn, page_setup
from src.dashboard.utils.tables import to_excel_bytes
from src.screener.engine import apply_filters, composite_score, load_config, load_universe, run_preset

page_setup("Financial Screener", "🔎")
cfg = load_config()


@st.cache_data(ttl=600, show_spinner=False)
def universe():
    u = load_universe(get_conn())
    u["composite_score"] = composite_score(u, cfg)
    return u


uni = universe()
# key, label, min, max, default ("off" value), step, screener_config filter name
SLIDERS = [
    ("s_roe", "Min ROE %", -20.0, 60.0, -20.0, 1.0, "min_roe"),
    ("s_de", "Max D/E (non-financials)", 0.0, 10.0, 10.0, 0.05, "max_de"),
    ("s_fcf", "Min FCF (₹ Cr)", -10000.0, 60000.0, -10000.0, 500.0, "min_fcf"),
    ("s_rev", "Min revenue CAGR 5Y %", -20.0, 60.0, -20.0, 1.0, "min_rev_cagr_5y"),
    ("s_pat", "Min PAT CAGR 5Y %", -20.0, 80.0, -20.0, 1.0, "min_pat_cagr_5y"),
    ("s_opm", "Min OPM % (non-financials)", -20.0, 80.0, -20.0, 1.0, "min_opm"),
    ("s_pe", "Max P/E (sim.)", 5.0, 80.0, 80.0, 1.0, "max_pe"),
    ("s_pb", "Max P/B (sim.)", 0.5, 15.0, 15.0, 0.5, "max_pb"),
    ("s_dy", "Min dividend yield % (sim.)", 0.0, 4.5, 0.0, 0.1, "min_div_yield"),
    ("s_icr", "Min interest coverage (x)", 0.0, 50.0, 0.0, 0.5, "min_icr"),
]
KEYS = [s[0] for s in SLIDERS]
DEFAULT = {s[0]: s[4] for s in SLIDERS}
FILTER_KEY = {s[6]: s[0] for s in SLIDERS}
PRESET_BUTTONS = [("Quality", "Quality Compounder"), ("Value", "Value Pick"), ("Growth", "Growth Accelerator"),
                  ("Dividend", "Dividend Champion"), ("Debt-Free", "Debt-Free Blue Chip"), ("Turnaround", "Turnaround Watch")]
for k, v in DEFAULT.items():
    st.session_state.setdefault(k, v)


def fill_preset(name: str) -> None:
    """Callback: write the preset's thresholds into the sliders (runs before the sliders are drawn)."""
    vals = dict(DEFAULT)
    for fname, thr in cfg["presets"][name]["filters"].items():
        if fname in FILTER_KEY:
            vals[FILTER_KEY[fname]] = float(thr)
    for k, v in vals.items():
        st.session_state[k] = v
    st.session_state["preset_name"], st.session_state["preset_snapshot"] = name, tuple(vals[k] for k in KEYS)


def reset() -> None:
    for k, v in DEFAULT.items():
        st.session_state[k] = v
    st.session_state["preset_name"] = st.session_state["preset_snapshot"] = None


side = st.sidebar
side.markdown("**Presets** (click to fill the sliders)")
cols = side.columns(2)
for i, (label, name) in enumerate(PRESET_BUTTONS):
    cols[i % 2].button(label, key=f"btn_{label}", on_click=fill_preset, args=(name,), width="stretch")
side.button("Reset filters", on_click=reset, width="stretch")
side.divider()
for key, label, lo, hi, _, step, _ in SLIDERS:
    side.slider(label, lo, hi, step=step, key=key)
sector = side.multiselect("Sector", sorted(uni["broad_sector"].dropna().unique()))

current = tuple(st.session_state[k] for k in KEYS)
base = uni[uni["broad_sector"].isin(sector)] if sector else uni
preset = st.session_state.get("preset_name")
if preset and st.session_state.get("preset_snapshot") == current:     # sliders untouched since the preset was applied
    res = run_preset(base, preset, cfg)
    f_cols = [cfg["filters"][f]["column"] for f in cfg["presets"][preset]["filters"]]
    extras = [f for f in cfg["presets"][preset]["filters"] if f not in FILTER_KEY]
    st.caption(f"Preset **{preset}** · ranked by {cfg['presets'][preset]['rank_by']}" + (f" · also applies: {', '.join(extras)}" if extras else "")
               + (" · and D/E declining" if cfg["presets"][preset].get("extra") else "") + " · move any slider to switch to custom filtering")
else:
    active = {fname: st.session_state[key] for key, _, _, _, default, _, fname in SLIDERS if st.session_state[key] != default}
    res = apply_filters(base, active, cfg).sort_values("composite_score", ascending=False)
    f_cols = [cfg["filters"][f]["column"] for f in active] or ["return_on_equity_pct", "debt_to_equity", "revenue_cagr_5y"]
show = ["company_id", "company_name", "broad_sector", "composite_score"] + [c for c in dict.fromkeys(f_cols) if c not in ("composite_score",)]
st.subheader(f"{len(res)} companies match your filters")
st.dataframe(res[show].round(2), hide_index=True, width="stretch")
a, b = st.columns(2)
a.download_button("⬇ CSV", res[show].round(2).to_csv(index=False), "screener_results.csv", "text/csv")
b.download_button("⬇ Excel", to_excel_bytes(res[show].round(2), "Screener"), "screener_results.xlsx",
                  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
st.caption("P/E, P/B and dividend yield come from the SIMULATED market dataset. Banks / NBFCs / insurers skip the D/E, ROCE, OPM and ICR filters.")
