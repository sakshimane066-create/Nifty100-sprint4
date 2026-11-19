"""Valuation module: multiples vs history and sector, flags, FCF yield, valuation_summary.xlsx.
All market data (market_cap.xlsx) is SIMULATED - outputs are labelled accordingly."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[2]
CAUTION_MULT, DISCOUNT_MULT, EV_PREMIUM = 1.5, 0.7, 1.20
MIN_SECTOR_SIZE = 4


def pe_flag(pe: float, sector_median_pe: float) -> str:
    """'Caution' if P/E > 1.5x sector median, 'Discount' if < 0.7x, else 'Fair' ('N/A' when a value is missing)."""
    if pd.isna(pe) or pd.isna(sector_median_pe):
        return "N/A"
    return "Caution" if pe > sector_median_pe * CAUTION_MULT else "Discount" if pe < sector_median_pe * DISCOUNT_MULT else "Fair"


def build_valuation(conn: sqlite3.Connection, fy: int = 2024) -> pd.DataFrame:
    """One row per company with current and 5-year median multiples, sector medians, ranks and flags."""
    mc = pd.read_sql("SELECT * FROM market_cap", conn)
    sec = pd.read_sql("SELECT s.company_id, s.broad_sector, c.company_name FROM sectors s JOIN companies c ON c.id=s.company_id", conn)
    cur = mc[mc["year"] == fy].drop(columns="year")
    hist = mc[mc["year"].between(fy - 4, fy)].groupby("company_id")[["pe_ratio", "pb_ratio", "ev_ebitda"]].median().add_suffix("_5y_median")
    fr = pd.read_sql("SELECT company_id, free_cash_flow_cr, return_on_equity_pct FROM financial_ratios WHERE is_latest=1", conn)
    v = sec.merge(cur, on="company_id").merge(hist, on="company_id").merge(fr, on="company_id", how="left")
    med = v.groupby("broad_sector")[["pe_ratio", "pb_ratio", "ev_ebitda"]].transform("median").add_prefix("sector_median_")
    v = pd.concat([v, med], axis=1)
    v["fcf_yield_pct"] = v["free_cash_flow_cr"] / v["market_cap_crore"] * 100
    n_sec = v.groupby("broad_sector")["company_id"].transform("count")
    big = n_sec >= MIN_SECTOR_SIZE  # medians of 2-3 companies are not a benchmark
    v["pe_flag"] = [pe_flag(a, b) if ok else "N/A" for a, b, ok in zip(v["pe_ratio"], v["sector_median_pe_ratio"], big)]
    v["flag_note"] = ["" if ok else f"Not assessed: sector has fewer than {MIN_SECTOR_SIZE} companies" for ok in big]
    v["pe_vs_sector_median_pct"] = (v["pe_ratio"] / v["sector_median_pe_ratio"] - 1) * 100
    v["ev_ebitda_flag"] = ((v["ev_ebitda"] > v["sector_median_ev_ebitda"] * EV_PREMIUM) & big).map({True: "Rich vs sector", False: ""})
    v["above_own_5y_pe"] = (v["pe_ratio"] > v["pe_ratio_5y_median"]).map({True: "Above 5Y median", False: ""})
    v["sector_pe_rank"] = v.groupby("broad_sector")["pe_ratio"].rank(method="min")
    v["dividend_yield_rank"] = v["dividend_yield_pct"].rank(ascending=False, method="min")
    v["fcf_yield_rank"] = v["fcf_yield_pct"].rank(ascending=False, method="min")
    return v.sort_values(["broad_sector", "pe_ratio"]).reset_index(drop=True)


def export_valuation(v: pd.DataFrame, out_dir: Path = ROOT / "output") -> None:
    """Write valuation_summary.xlsx (with notes sheet) and valuation_flags.csv."""
    out_dir.mkdir(exist_ok=True)
    path = out_dir / "valuation_summary.xlsx"
    notes = pd.DataFrame({"Note": [
        "SIMULATED DATA: market_cap.xlsx is a simulated dataset. Do not draw investment conclusions.",
        "flag: Caution = P/E > 1.5 x sector median; Discount = P/E < 0.7 x sector median; otherwise Fair. N/A = sector has fewer than 4 companies (median not a benchmark).",
        "Rich vs sector = EV/EBITDA more than 20% above sector median (spec 6.3).",
        "FCF yield = free cash flow (CFO+CFI, Rs Cr, latest FY) / simulated market cap x 100. Market caps in the simulated file are",
        "  not consistent with real earnings, so FCF yield values are indicative of method only.",
        "Sector medians use the 10 broad sectors in sectors.xlsx; sectors with fewer than 4 companies (Communication Services, Real Estate) get no flags.",
    ]})
    required = pd.DataFrame({
        "company_id": v["company_id"], "company_name": v["company_name"], "sector": v["broad_sector"], "P/E": v["pe_ratio"], "P/B": v["pb_ratio"],
        "EV/EBITDA": v["ev_ebitda"], "FCF_yield_pct": v["fcf_yield_pct"], "5yr_median_PE": v["pe_ratio_5y_median"],
        "PE_vs_sector_median_pct": v["pe_vs_sector_median_pct"], "flag": v["pe_flag"]})
    extras = v[["sector_median_pe_ratio", "ev_ebitda_flag", "above_own_5y_pe", "sector_pe_rank", "dividend_yield_pct", "dividend_yield_rank", "fcf_yield_rank", "flag_note"]]
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        pd.concat([required, extras], axis=1).round(2).to_excel(xw, sheet_name="Valuation", index=False)
        notes.to_excel(xw, sheet_name="Notes", index=False)
    wb = load_workbook(path)
    ws = wb["Valuation"]
    for c in ws[1]:
        c.font, c.fill = Font(bold=True, name="Arial", color="FFFFFF"), PatternFill("solid", fgColor="1F3864")
    hdr = {c.value: c.column for c in ws[1]}
    fills = {"Caution": "F8CBAD", "Discount": "C6E0B4"}
    for row in ws.iter_rows(min_row=2):
        f = row[hdr["flag"] - 1]
        if f.value in fills:
            f.fill = PatternFill("solid", fgColor=fills[f.value])
    for i in range(1, ws.max_column + 1):
        ws.column_dimensions[get_column_letter(i)].width = 16
    ws.freeze_panes = "C2"
    wb["Notes"].column_dimensions["A"].width = 120
    wb.save(path)
    flags = v[v["pe_flag"].isin(["Caution", "Discount"])][
        ["company_id", "company_name", "broad_sector", "pe_ratio", "sector_median_pe_ratio", "pe_flag", "ev_ebitda", "sector_median_ev_ebitda", "ev_ebitda_flag"]]
    flags.assign(rationale=lambda d: d.apply(lambda r: f"P/E {r.pe_ratio} vs sector median {r.sector_median_pe_ratio:.1f} ({r.pe_ratio / r.sector_median_pe_ratio - 1:+.0%})", axis=1)
                 ).to_csv(out_dir / "valuation_flags.csv", index=False)


if __name__ == "__main__":
    with sqlite3.connect(ROOT / "data" / "nifty100.db") as c:
        df = build_valuation(c)
    export_valuation(df)
    print(df.shape, df["pe_flag"].value_counts().to_dict())
