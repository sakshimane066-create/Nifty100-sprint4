"""Normalisers for fiscal-year labels and NSE tickers."""
from __future__ import annotations

import re

PARSE_ERROR = "PARSE_ERROR"
TTM = "TTM"
_MONTHS = {
    m: i + 1
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    )
}
_YEAR_OK = re.compile(r"^\d{4}-\d{2}$")
# "Mar 2023", "Mar-23", "March-2023", "Dec 2012", optional suffix ("9m", "15")
_MON_YEAR = re.compile(r"^([a-z]{3})[a-z]*[\s\-/]*(\d{2}|\d{4})(?:\s+(\d{1,2})\s*m?)?$")
_FY = re.compile(r"^fy[\s\-]*(\d{2}|\d{4})$")
_YEAR_ONLY = re.compile(r"^(\d{4})(?:\.0+)?$")


def _full_year(y: str) -> int:
    return int(y) if len(y) == 4 else 2000 + int(y)


def normalize_year(raw: object) -> str:
    """Convert a raw fiscal-year label to 'YYYY-MM', 'TTM' or 'PARSE_ERROR'."""
    if raw is None:
        return PARSE_ERROR
    s = str(raw).strip().lower()
    if not s or s == "nan":
        return PARSE_ERROR
    if s == "ttm":
        return TTM
    if _YEAR_OK.match(s):
        return s
    if (m := _YEAR_ONLY.match(s)) is not None:
        return f"{m.group(1)}-03"  # bare year -> assume March FY close
    if (m := _FY.match(s)) is not None:
        return f"{_full_year(m.group(1))}-03"
    if (m := _MON_YEAR.match(s)) is not None and m.group(1) in _MONTHS:
        return f"{_full_year(m.group(2))}-{_MONTHS[m.group(1)]:02d}"
    return PARSE_ERROR


def period_months(raw: object) -> int:
    """Length of the reporting period in months (12 unless the label says otherwise)."""
    s = str(raw).strip().lower()
    if (m := _MON_YEAR.match(s)) is not None and m.group(3):
        return int(m.group(3))
    return 12


def fiscal_year(year_label: str) -> int | None:
    """Return the calendar year of a 'YYYY-MM' label (the fy key used to join market_cap)."""
    return int(year_label[:4]) if _YEAR_OK.match(year_label or "") else None


# Known source typos (cashflow.xlsx spells Adani Total Gas as AGTL)
TICKER_ALIASES = {"AGTL": "ATGL"}


def normalize_ticker(raw: object) -> str:
    """Strip whitespace, upper-case and de-alias an NSE ticker (hyphen and & are preserved)."""
    t = "" if raw is None else str(raw).strip().upper()
    return TICKER_ALIASES.get(t, t)
