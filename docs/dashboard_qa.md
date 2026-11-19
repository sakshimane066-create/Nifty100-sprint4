# Dashboard QA log (Sprint 4, Day 27)
Automated (`tests/dashboard/`): every page renders; Profile / Trends / Annual Reports for 10 tickers across IT, Financials, FMCG, Energy and
Healthcare (TCS, INFY, HDFCBANK, SBIN, HINDUNILVR, NESTLEIND, RELIANCE, NTPC, SUNPHARMA, CIPLA) and 4 partial-history companies
(JIOFIN, LICI, ATGL, ADANIGREEN); Screener: all 6 preset buttons, all sliders at minimum and at maximum, default = 92 companies;
unknown ticker message; "Data available" note for short history.

| Check | Result |
|---|---|
| All screens load for the test tickers | Pass |
| Partial-data companies: no crash + data-available note | Pass |
| Screener extreme slider values | Pass (no crash) |
| Missing values shown as N/A / dash | Pass |
| Chart overflow | Plotly charts use full container width (manual look: OK in screenshots) |
| Screener CSV / Excel download | Verified manually (opened in Excel) |
| Profile load < 3 s (AC-08) | Harness: 0.2-0.6 s cold for 5 tickers. **Add your own stopwatch result: ______** |
