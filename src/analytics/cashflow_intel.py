"""Cash Flow Intelligence (Module 7): earnings quality, CapEx intensity, FCF growth/conversion, deleveraging, distress."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from src.analytics.ratios import cagr
from src.utils.excel import to_excel_bytes

ROOT = Path(__file__).resolve().parents[2]
NA_FIN = "N/A (Financial)"


# ---------------------------------------------------------------- pure classifiers
def cfo_quality(ratio: float | None) -> str:
    """CFO / PAT over 5 years: >1.0 High Quality Earnings, <0.5 Accrual Risk, else Moderate."""
    if ratio is None or pd.isna(ratio):
        return "Insufficient data"
    return "High Quality Earnings" if ratio > 1.0 else "Accrual Risk" if ratio < 0.5 else "Moderate"


def capex_category(pct: float | None) -> str:
    """CapEx / revenue %: <3 Light (asset-light), >8 Heavy (capital intensive), else Moderate."""
    if pct is None or pd.isna(pct):
        return "Insufficient data"
    return "Light" if pct < 3 else "Heavy" if pct > 8 else "Moderate"


def fcf_tier(conv_pct: float | None) -> str:
    """FCF / EBITDA %: >60 Efficient, <30 CapEx Heavy, else Moderate."""
    if conv_pct is None or pd.isna(conv_pct):
        return "Insufficient data"
    return "Efficient" if conv_pct > 60 else "CapEx Heavy" if conv_pct < 30 else "Moderate"


def is_deleveraging(cff: float, debt_now: float, debt_prev: float) -> bool:
    """Financing outflow while borrowings fell year-on-year."""
    return bool(pd.notna(cff) and pd.notna(debt_now) and pd.notna(debt_prev) and cff < 0 and debt_now < debt_prev)


def is_distress(cfo: float, cff: float) -> bool:
    """Operating cash outflow funded by financing inflow."""
    return bool(pd.notna(cfo) and pd.notna(cff) and cfo < 0 and cff > 0)


# ---------------------------------------------------------------- engine
def _load(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql(
        """SELECT r.company_id, r.fy, r.year, r.is_financial, r.sales_cr, r.operating_profit_cr, r.net_profit_cr,
                  r.cash_from_operations_cr AS cfo, r.free_cash_flow_cr AS fcf, r.capex_cr, r.capex_intensity_pct,
                  r.total_debt_cr, r.capital_allocation, c.investing_activity AS cfi, c.financing_activity AS cff
           FROM financial_ratios r LEFT JOIN cashflow c ON c.company_id = r.company_id AND c.year = r.year
           ORDER BY r.company_id, r.fy""", conn)


def _fcf_cagr(g: pd.DataFrame, n: int) -> tuple[float | None, str]:
    s = g.set_index("fy")["fcf"]
    last = g["fy"].max()
    if (last - n) not in s.index:
        return None, "INSUFFICIENT"
    return cagr(s[last - n], s[last], n)


def build_intelligence(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (one row per company, distress alert rows)."""
    rows, alerts = [], []
    for cid, g in df.groupby("company_id"):
        g = g.sort_values("fy").reset_index(drop=True)
        last, fin = g.iloc[-1], bool(g.iloc[-1]["is_financial"])
        t5 = g.tail(5)
        pat5 = t5["net_profit_cr"].sum()
        cfo_pat = t5["cfo"].sum() / pat5 if t5["cfo"].notna().sum() >= 4 and pat5 > 0 else np.nan
        ebitda5 = t5["operating_profit_cr"].sum()
        conv = t5["fcf"].sum() / ebitda5 * 100 if t5["fcf"].notna().sum() >= 4 and ebitda5 > 0 else np.nan
        capex_avg = (t5["capex_cr"].sum() / t5["sales_cr"].sum() * 100) if t5["capex_cr"].notna().sum() >= 4 and t5["sales_cr"].sum() > 0 else np.nan
        g["debt_prev"] = g["total_debt_cr"].shift(1)
        delev = [is_deleveraging(a, b, c) for a, b, c in zip(g["cff"], g["total_debt_cr"], g["debt_prev"])]
        g["delev"] = delev
        g["distress"] = [is_distress(a, b) for a, b in zip(g["cfo"], g["cff"])]
        last = g.iloc[-1]  # re-read: now includes delev / distress / debt_prev
        f5, f10 = _fcf_cagr(g, 5), _fcf_cagr(g, 10)
        rows.append(dict(
            company_id=cid, fy=int(last["fy"]), is_financial=int(fin),
            cfo_pat_5y=None if pd.isna(cfo_pat) else round(cfo_pat, 2), cfo_quality=NA_FIN if fin else cfo_quality(cfo_pat),
            capex_intensity_pct=None if pd.isna(last["capex_intensity_pct"]) else round(last["capex_intensity_pct"], 2),
            capex_intensity_5y_pct=None if pd.isna(capex_avg) else round(capex_avg, 2), capex_category=NA_FIN if fin else capex_category(capex_avg),
            fcf_cagr_5y=None if f5[0] is None else round(f5[0], 2), fcf_cagr_5y_flag=f5[1],
            fcf_cagr_10y=None if f10[0] is None else round(f10[0], 2), fcf_cagr_10y_flag=f10[1],
            fcf_conversion_5y_pct=None if pd.isna(conv) else round(conv, 1), fcf_conversion_tier=NA_FIN if fin else fcf_tier(conv),
            deleveraging_latest=int(bool(last["delev"])), deleveraging_years_5y=int(g["delev"].tail(5).sum()),
            distress_latest=int(bool(last["distress"]) and not fin), distress_years_3y=0 if fin else int(g["distress"].tail(3).sum()),
            capital_allocation=last["capital_allocation"], fcf_latest_cr=last["fcf"], cfo_latest_cr=last["cfo"]))
        if not fin:
            for _, y in g.tail(3).iterrows():
                if y["distress"]:
                    alerts.append(dict(company_id=cid, fy=int(y["fy"]), cfo_cr=y["cfo"], cfi_cr=y["cfi"], cff_cr=y["cff"], borrowings_cr=y["total_debt_cr"],
                                       borrowings_change_cr=None if pd.isna(y["debt_prev"]) or pd.isna(y["total_debt_cr"]) else y["total_debt_cr"] - y["debt_prev"],
                                       net_profit_cr=y["net_profit_cr"], is_latest_year=int(y["fy"] == last["fy"]),
                                       reason="CFO < 0 and CFF > 0: operations funded by financing"))
    return pd.DataFrame(rows), pd.DataFrame(alerts, columns=["company_id", "fy", "cfo_cr", "cfi_cr", "cff_cr", "borrowings_cr", "borrowings_change_cr",
                                                              "net_profit_cr", "is_latest_year", "reason"])


def build_cashflow_intelligence(db_path: Path = ROOT / "data" / "nifty100.db", out_dir: Path = ROOT / "output") -> dict:
    """Write the cashflow_intelligence table, cashflow_intelligence.xlsx and distress_alerts.csv."""
    out_dir.mkdir(exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        ci, alerts = build_intelligence(_load(conn))
        meta = pd.read_sql("SELECT c.id AS company_id, c.company_name, s.broad_sector FROM companies c JOIN sectors s ON s.company_id = c.id", conn)
        ci = meta.merge(ci, on="company_id").sort_values(["broad_sector", "company_id"])
        alerts = alerts.merge(meta[["company_id", "company_name"]], on="company_id", how="left")
        ci.to_sql("cashflow_intelligence", conn, if_exists="replace", index=False)
    alerts.to_csv(out_dir / "distress_alerts.csv", index=False)
    notes = pd.DataFrame({"Note": [
        "CFO quality = 5-year cumulative CFO / cumulative PAT (>1.0 High Quality Earnings, <0.5 Accrual Risk).",
        "CapEx intensity uses |investing cash flow| / sales as the CapEx proxy (spec); investing flow can include non-CapEx items such as investment sales.",
        "FCF = CFO + CFI (spec). FCF conversion = 5-year cumulative FCF / cumulative EBITDA (operating profit). >60% Efficient, <30% CapEx Heavy.",
        "FCF CAGR is blank when the base year is <= 0 or history is too short; see the *_flag columns (TURNAROUND, BOTH_NEGATIVE, DECLINE_TO_LOSS, INSUFFICIENT).",
        "Deleveraging = financing outflow with borrowings lower than the previous year. Distress = CFO < 0 and CFF > 0 (non-financials only).",
        "Banks, NBFCs and insurers are excluded from quality / CapEx / conversion tiers: loan flows sit inside operating cash flow.",
    ]})
    xlsx = to_excel_bytes(ci.round(2), "Cash Flow Intelligence")
    from openpyxl import load_workbook
    from openpyxl.styles import PatternFill
    import io
    wb = load_workbook(io.BytesIO(xlsx))
    ws = wb["Cash Flow Intelligence"]
    hdr = {c.value: c.column for c in ws[1]}
    fills = {"High Quality Earnings": "C6E0B4", "Accrual Risk": "F8CBAD", "Efficient": "C6E0B4", "CapEx Heavy": "FFE699"}
    for row in ws.iter_rows(min_row=2):
        for col in ("cfo_quality", "fcf_conversion_tier"):
            cell = row[hdr[col] - 1]
            if cell.value in fills:
                cell.fill = PatternFill("solid", fgColor=fills[cell.value])
        if row[hdr["distress_latest"] - 1].value == 1:
            row[hdr["distress_latest"] - 1].fill = PatternFill("solid", fgColor="F8CBAD")
    ns = wb.create_sheet("Notes")
    ns.append(["Note"])
    for t in notes["Note"]:
        ns.append([t])
    ns.column_dimensions["A"].width = 150
    wb.save(out_dir / "cashflow_intelligence.xlsx")
    return {"companies": len(ci), "high_quality": int((ci.cfo_quality == "High Quality Earnings").sum()), "accrual_risk": int((ci.cfo_quality == "Accrual Risk").sum()),
            "distress_latest": int(ci.distress_latest.sum()), "alerts": len(alerts)}


if __name__ == "__main__":
    print(build_cashflow_intelligence())
