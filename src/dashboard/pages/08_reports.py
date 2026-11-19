"""Annual Reports: clickable BSE PDF links per year; red 'Report unavailable' badge for missing or 404 links."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # project root, so `import src...` works under `streamlit run`

import requests
import streamlit as st

from src.dashboard.utils.db import company_picker, page_setup, query

page_setup("Annual Reports", "📄")


@st.cache_data(ttl=3600, show_spinner=False)
def link_status(url: str) -> int:
    """HTTP status of a report URL (0 = could not be reached). Cached for an hour."""
    try:
        return requests.head(url, timeout=4, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}).status_code
    except requests.RequestException:
        return 0


t = company_picker("Search company name or ticker", sidebar=True)
d = query("SELECT year, annual_report FROM documents WHERE company_id=? ORDER BY year DESC", (t,))
if d.empty:
    st.markdown(":red-badge[Report unavailable]  No annual reports on file for this company.")
    st.stop()
yrs = st.sidebar.slider("Year range", int(d.year.min()), int(d.year.max()), (int(d.year.min()), int(d.year.max())))
verify = st.sidebar.checkbox("Verify links (HTTP check, slower)", value=False)
missing = bad = 0
for y in range(yrs[1], yrs[0] - 1, -1):
    row = d[d.year == y]
    link = row.annual_report.iloc[0] if not row.empty else None
    if not link:
        missing += 1
        st.markdown(f"**{y}** · :red-badge[Report unavailable]")
        continue
    code = link_status(link) if verify else None
    if code in (404, 410):
        bad += 1
        st.markdown(f"**{y}** · :red-badge[Report unavailable] (HTTP {code})")
    elif code == 0:
        st.markdown(f"**{y}** · [Open annual report ↗]({link}) :gray-badge[could not verify]")
    else:
        st.markdown(f"**{y}** · [Open annual report ↗]({link})")
st.caption(f"{len(d)} reports on file · {missing} year(s) without a link" + (f" · {bad} broken link(s) found" if verify else " · tick 'Verify links' to check each URL for 404s"))
