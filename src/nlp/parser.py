"""Parse the text fields of analysis.xlsx ('10 Years: 21%', 'TTM: 47%', 'Last Year: 17%') into numbers."""
from __future__ import annotations

import re

import pandas as pd

# Spec regex r'(\d+)\s*Years?:?\s*([\d.]+)%' extended for TTM / Last Year / negative values / odd spacing
PATTERN = re.compile(r"^\s*(?P<label>\d+\s*Years?|TTM|Last\s*Year)\s*:?\s*(?P<val>-?\d+(?:\.\d+)?)\s*%\s*$", re.I)
METRICS = {
    "compounded_sales_growth": "sales_growth_cagr",
    "compounded_profit_growth": "profit_growth_cagr",
    "stock_price_cagr": "stock_price_cagr",
    "roe": "roe",
}


def parse_cell(text: object) -> tuple[str, int | None, float] | None:
    """Return (period_label, period_years, value_pct) or None if the text is not in a known format."""
    if not isinstance(text, str):
        return None
    m = PATTERN.match(text)
    if not m:
        return None
    label = re.sub(r"\s+", "", m.group("label")).lower()
    value = float(m.group("val"))
    if label == "ttm":
        return "TTM", None, value
    if label == "lastyear":
        return "LastYear", 1, value
    years = int(re.match(r"\d+", label).group())
    return f"{years}Y", years, value


def parse_analysis(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Long table (company_id, metric_type, period, period_years, value_pct) + a table of unparseable cells."""
    ok, bad = [], []
    for _, row in df.iterrows():
        for col, metric in METRICS.items():
            parsed = parse_cell(row[col])
            if parsed is None:
                if isinstance(row[col], str):
                    bad.append(dict(company_id=row["company_id"], column=col, raw=row[col]))
                continue
            label, years, val = parsed
            ok.append(dict(company_id=row["company_id"], metric_type=metric, period=label, period_years=years, value_pct=val))
    return pd.DataFrame(ok, columns=["company_id", "metric_type", "period", "period_years", "value_pct"]), pd.DataFrame(
        bad, columns=["company_id", "column", "raw"])


def cross_validate(parsed: pd.DataFrame, ratios: pd.DataFrame, tol_pts: float = 5.0) -> pd.DataFrame:
    """Compare parsed 3/5/10Y figures with the ratio engine; flag differences above `tol_pts` percentage points."""
    rows = []
    for _, p in parsed[parsed["period_years"].isin([3, 5, 10]) & (parsed["period"] != "LastYear")].iterrows():
        n = int(p["period_years"])
        r = ratios[ratios["company_id"] == p["company_id"]].sort_values("fy")
        if r.empty:
            continue
        last = r.iloc[-1]
        if p["metric_type"] == "sales_growth_cagr":
            engine, name = last.get(f"revenue_cagr_{n}y"), f"revenue_cagr_{n}y"
        elif p["metric_type"] == "profit_growth_cagr":
            engine, name = last.get(f"pat_cagr_{n}y"), f"pat_cagr_{n}y"
        elif p["metric_type"] == "roe":
            engine, name = r["return_on_equity_pct"].tail(n).mean(), f"avg_roe_last_{n}y"
        else:
            continue
        diff = None if pd.isna(engine) else round(float(engine) - p["value_pct"], 2)
        rows.append(dict(company_id=p["company_id"], metric=p["metric_type"], period_years=n, source_pct=p["value_pct"],
                         engine_metric=name, engine_pct=None if pd.isna(engine) else round(float(engine), 2),
                         diff_pts=diff, flag="NO_ENGINE_VALUE" if diff is None else ("DIVERGES" if abs(diff) > tol_pts else "OK")))
    return pd.DataFrame(rows)
