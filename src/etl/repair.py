"""Source-data repairs applied at load time (each one is logged as a DQ record)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

OVERRIDES = Path(__file__).resolve().parents[2] / "config" / "company_overrides.yaml"


def swapped_ops_mask(pl: pd.DataFrame) -> pd.Series:
    """Rows where `operating_profit` holds total expenses and `opm_percentage` holds the real operating profit.

    Signature: sales - operating_profit == opm_percentage (an exact accounting identity only if the two are swapped),
    while opm_percentage does NOT equal operating_profit / sales x 100. Tiny sales are ignored to avoid coincidences.
    """
    gap = (pl["sales"] - pl["operating_profit"] - pl["opm_percentage"]).abs()
    margin = pl["operating_profit"] / pl["sales"].where(pl["sales"] > 0) * 100
    return (pl["sales"] > 500) & (gap <= 2 + 0.002 * pl["sales"].abs()) & ((pl["opm_percentage"] - margin).abs() > 1)


def repair_swapped_ops(pl: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (repaired frame, the rows that were swapped as they were in the source)."""
    mask = swapped_ops_mask(pl)
    bad = pl[mask].copy()
    out = pl.copy()
    out.loc[mask, "operating_profit"] = pl.loc[mask, "opm_percentage"]
    out.loc[mask, "opm_percentage"] = (out.loc[mask, "operating_profit"] / pl.loc[mask, "sales"] * 100).round(2)
    return out, bad


def apply_overrides(companies: pd.DataFrame, sectors: pd.DataFrame, path: Path = OVERRIDES) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Apply config/company_overrides.yaml; returns (companies, sectors, log of what changed)."""
    log = []
    if not Path(path).exists():
        return companies, sectors, pd.DataFrame(columns=["company_id", "field", "old", "new"])
    companies, sectors = companies.copy(), sectors.copy()
    for cid, spec in (yaml.safe_load(Path(path).read_text()) or {}).items():
        if "about_company" in spec and (companies["id"] == cid).any():
            idx = companies["id"] == cid
            old = companies.loc[idx, "about_company"].iloc[0]
            new = " ".join(str(spec["about_company"]).split())
            companies.loc[idx, "about_company"] = new
            log.append(dict(company_id=cid, field="about_company", old=str(old)[:60], new=new[:60]))
        for field, new in (spec.get("sector") or {}).items():
            idx = sectors["company_id"] == cid
            if idx.any():
                old = sectors.loc[idx, field].iloc[0]
                sectors.loc[idx, field] = new
                log.append(dict(company_id=cid, field=field, old=old, new=new))
    return companies, sectors, pd.DataFrame(log, columns=["company_id", "field", "old", "new"])
