"""Company logo resolution: website favicon -> source URL (server-verified) -> generated ticker badge."""
from __future__ import annotations

import hashlib
from urllib.parse import urlparse

import requests
import streamlit as st

HEADERS = {"User-Agent": "Mozilla/5.0 (N100-dashboard)"}
FAVICON = "https://www.google.com/s2/favicons?domain={domain}&sz=128"


def domain_of(website: str | None) -> str | None:
    """Bare domain of a website URL (no scheme / www / path)."""
    if not website or not isinstance(website, str):
        return None
    host = urlparse(website if "://" in website else f"https://{website}").netloc.lower()
    return host.removeprefix("www.") or None


def badge_svg(ticker: str, size: int = 110) -> str:
    """Deterministic coloured tile with the ticker's first letters (never blank, never wrong)."""
    hue = int(hashlib.md5(ticker.encode()).hexdigest()[:4], 16) % 360
    text = "".join(ch for ch in ticker if ch.isalnum())[:3] or "?"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 100 100">'
            f'<rect width="100" height="100" rx="16" fill="hsl({hue},55%,38%)"/>'
            f'<text x="50" y="58" font-family="Arial,sans-serif" font-size="30" font-weight="700" fill="#fff" '
            f'text-anchor="middle">{text}</text></svg>')


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_image(url: str) -> bytes | None:
    """Download an image server-side; None unless it is a real image (HTTP 200, image/*, > 300 bytes)."""
    try:
        r = requests.get(url, timeout=2, headers=HEADERS)
    except requests.RequestException:
        return None
    ok = r.status_code == 200 and r.headers.get("content-type", "").startswith("image") and len(r.content) > 300
    return r.content if ok else None


def logo_for(ticker: str, website: str | None, source_url: str | None, source_is_unique: bool = True) -> bytes | str:
    """Return image bytes if any real logo could be fetched, else an SVG badge string."""
    dom = domain_of(website)
    if dom and (img := fetch_image(FAVICON.format(domain=dom))):
        return img
    if source_url and source_is_unique and (img := fetch_image(source_url)):
        return img
    return badge_svg(ticker)
