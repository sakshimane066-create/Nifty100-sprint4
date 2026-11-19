# Sprint 4 retrospective - Dashboard & Valuation

## Delivered
Streamlit app (`src/dashboard/app.py` + 8 spec screens + Valuation and Cash Flow pages), cached loaders in `utils/db.py`
(`get_companies/get_ratios/get_pl/get_bs/get_cf/get_sectors/get_peers/get_valuation`, all `@st.cache_data(ttl=600)` via `query()`),
`src/analytics/valuation.py`, `output/valuation_summary.xlsx` (92 rows, spec columns first) and `output/valuation_flags.csv`.

## UX decisions
* Unmoved screener sliders count as "off" so a fresh page shows all 92 companies; preset buttons fill the sliders and the full preset
  (including conditions that have no slider) stays active until a slider is moved.
* Banks / NBFCs / insurers: ROCE, D/E, OPM and ICR are shown as n/m or skipped - their balance sheets and P&L layouts are different.
* Missing values display as N/A (or a dash on grey in tables) instead of "None" / NaN.
* Logos: website favicon -> verified source URL -> generated ticker badge (85 of 92 source URLs are dead).

## Data edge cases found while building the dashboard
Scale-mismatched balance sheets (BEL, HAL, INDIGO, LT) -> DQ-17; swapped operating-profit columns (9 companies, 107 rows) -> DQ-18;
wrong LT description and ABB sector -> overrides (DQ-19); SBIN has no balance sheet; 8 tickers missing from `companies.xlsx`;
sectors with < 4 companies get no valuation flag. Details: `docs/data_findings.md`.

## Performance
Company Profile cold render 0.2-0.6 s for 5 tickers in the test harness (`tests/dashboard/measure_profile_load.py`), 0.04-0.09 s cached.
Browser paint and the first favicon download add a little; re-measure with a stopwatch on your own machine for AC-08.

## Environment finding
matplotlib can be blocked by Windows Application Control. Fix: matplotlib made optional (dashboard needs none; PDFs fall back to vector charts).

## Spec deviations
10 sectors in the data (spec: 11); Home shows "N sectors in the data"; valuation `flag` is N/A for sectors with fewer than 4 companies;
8 spec screens + 2 extra pages.
