"""Business-description tagger: keyword-classify about_company text into a broad sector and validate vs sectors.xlsx."""
from __future__ import annotations

import re

import pandas as pd

KEYWORDS: dict[str, list[str]] = {
    "Financials": ["bank", "insurance", "lending", "nbfc", "finance", "financial services", "loans", "mutual fund", "asset management", "housing finance"],
    "Information Technology": ["it services", "software", "consulting", "digital", "technology services", "cloud", "outsourcing", "it solutions"],
    "Energy": ["oil", "natural gas", "gas distribution", "refin", "power generation", "power transmission", "electricity", "petroleum",
               "renewable", "solar", "hydro", "hydrocarbon", "thermal power", "power utility"],
    "Consumer Discretionary": ["automobile", "motorcycle", "two-wheeler", "vehicles", "cars", "retail", "airline", "jewel", "hotel", "travel",
                               "tourism", "e-commerce", "supermarket", "auto components", "tyres"],
    "Consumer Staples": ["fmcg", "food", "beverage", "consumer goods", "personal care", "tea", "biscuit", "dairy", "tobacco", "cigarette", "packaged"],
    "Healthcare": ["pharma", "drug", "medicine", "hospital", "healthcare", "formulation", "generic", "nutraceutical", "api's", "active pharmaceutical"],
    "Materials": ["steel", "cement", "aluminium", "mining", "chemical", "paint", "zinc", "copper", "fertili", "metals", "iron ore"],
    "Industrials": ["engineering", "construction", "defence", "aerospace", "aeronautic", "aircraft", "capital goods", "electrical", "infrastructure",
                    "railway", "shipbuilding", "equipment", "electronics", "industrial", "manufacturing industries", "power distribution equipment"],
    "Communication Services": ["telecom", "mobile services", "broadband", "wireless", "online platform", "classifieds", "job portal"],
    "Real Estate": ["real estate", "residential", "housing", "property", "developer", "township"],
}


def tag_description(text: object) -> tuple[str | None, dict[str, int]]:
    """Return (best sector or None, keyword-hit counts per sector)."""
    if not isinstance(text, str) or not text.strip():
        return None, {}
    low = text.lower()
    hits = {s: sum(len(re.findall(r"\b" + re.escape(k), low)) for k in kws) for s, kws in KEYWORDS.items()}  # word-prefix match: "oil" != "soil"
    hits = {s: n for s, n in hits.items() if n}
    return (max(hits, key=hits.get) if hits else None), hits


def validation_report(companies: pd.DataFrame, sectors: pd.DataFrame) -> pd.DataFrame:
    """Per-company tag vs sectors.xlsx broad_sector."""
    m = companies[["id", "about_company"]].merge(sectors[["company_id", "broad_sector"]], left_on="id", right_on="company_id")
    rows = []
    for _, r in m.iterrows():
        tag, hits = tag_description(r["about_company"])
        rows.append(dict(company_id=r["id"], predicted_sector=tag, actual_sector=r["broad_sector"],
                         match=int(tag == r["broad_sector"]), keyword_hits=sum(hits.values()), no_text=int(tag is None)))
    return pd.DataFrame(rows)
