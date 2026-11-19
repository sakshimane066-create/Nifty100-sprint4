# N100 Financial Intelligence Platform

Analytics platform for 92 Nifty 100 companies built from 12 Bluestock Excel datasets: ETL -> SQLite -> 30+ KPIs -> screener -> peer comparison -> valuation -> Streamlit dashboard.

## Quick start (about 5 minutes)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config/.env.template .env
python -m src.pipeline   # Windows-friendly: rebuilds EVERYTHING in order (add --reports for PDFs)
make all          # same thing with make: load -> ratios -> peers -> valuation -> nlp -> cashflow -> reports
# one-time (optional, better sentiment): python -c "import nltk; nltk.download('vader_lexicon')"
make test         # 131 tests, ~96% coverage
make dashboard    # http://localhost:8501
```
Data files already sit in `data/raw/` (7 core, read-only) and `data/supporting/` (5 supplementary).

## What is built
| Sprint | Status | Where |
|---|---|---|
| 1 ETL, 18 DQ rules (16 from the spec + DQ-17 scale check + DQ-18 swapped columns), SQLite, audit logs | Done | `src/etl/`, `output/load_audit.csv`, `output/validation_failures.csv`, `docs/exploratory_queries.sql` |
| 2 Ratio engine (40+ KPI columns, CAGR flags, capital allocation) | Done | `src/analytics/ratios.py`, `output/capital_allocation.csv`, `output/ratio_edge_cases.log` |
| 3 Screener (18 filters, 6 presets, composite score), peer percentiles | Done | `src/screener/engine.py`, `config/screener_config.yaml`, `src/analytics/peer.py` |
| 4 Dashboard (8 screens + valuation) and valuation module | Done | `src/dashboard/`, `src/analytics/valuation.py`, `output/valuation_summary.xlsx` |
| 5 NLP, cash-flow intelligence, PDF reports | Done | `src/nlp/`, `src/analytics/cashflow_intel.py`, `src/reports/`, `output/*.csv|xlsx`, `reports/` |
| 6 API (16 endpoints), KMeans clustering, final QA | **Not started** | |

Not yet produced: `screener_output.xlsx`, `peer_comparison.xlsx`, `radar_charts/` PNGs (the dashboard renders radars live).

## Design decisions (spec ambiguities)
* The spec contradicts itself (14 vs 18 DQ rules (16 from the spec + DQ-17 scale check + DQ-18 swapped columns), 50/30/20 vs 35/30/20/15 score weights, 5 vs 8 screens...). I followed the **detailed sections**: 16 DQ rules, 8 screens, 16 endpoints, 23 deliverables; composite score weights from section 25.1.
* `financial_ratios` (computed) is separate from `financial_ratios_source` (Bluestock file, used only to cross-validate).
* FCF = CFO + CFI and CapEx = |CFI| exactly as specified; CFI can include non-CapEx items (and be positive), so treat as proxies.
* Financials (banks/NBFC/insurers): D/E, ICR and ROCE filters are skipped (carve-out); leverage scores 50 (neutral) in the composite score. `Debt-Free Blue Chip` disables the carve-out.
* D/E <= 0.05 counts as debt-free for the preset (spec says = 0; exact zero is too strict).
* `Composite Quality Score` (0.30 ROE + 0.25 FCF conversion + 0.25 ROCE + 0.20 D/E, P10/P90 winsorised, per year x financial/non-financial group) is stored in `financial_ratios`. The spec does not define "FCF_score", so FCF conversion is used.
* Peer percentiles are oriented so higher = better (D/E inverted).

## Read this: data issues
See `docs/data_findings.md`. Most important: **8 tickers exist in the financial files but not in `companies.xlsx`** (WIPRO, VEDL, ZOMATO, ULTRACEMCO, UNIONBANK, UNITDSPR, VBL, ZYDUSLIFE) and are rejected as orphans; SBIN has no balance sheet; market data is simulated.

## Layout
`src/etl` `src/analytics` `src/screener` `src/dashboard` · `config/` · `tests/` · `output/` · `docs/`

## Dashboard screens (`streamlit run src/dashboard/app.py`)
| # | Page file | What you see |
|---|---|---|
| 1 | `01_home.py` | 6 KPI tiles (average ROE, median P/E, median D/E, total companies, median revenue CAGR 5Y, debt-free count), sector donut, top-5 quality table, fiscal-year selector 2019-2024 |
| 2 | `02_profile.py` | Searchable company picker, card (name, NSE ticker, sector, description, logo), 6 KPI tiles (ROE, ROCE, net margin, D/E, revenue CAGR 5Y, FCF), revenue / profit bars, ROE-ROCE dual-axis line, liabilities and cash-flow charts, pros and cons with green check / red cross, tearsheet PDF download |
| 3 | `03_screener.py` | 10 sidebar sliders, 6 preset buttons that fill the sliders, live results table with a "N companies match your filters" label, CSV and Excel download |
| 4 | `04_peers.py` | Peer-group dropdown, selected-company radar vs peer average and benchmark, side-by-side KPI table (benchmark row highlighted), percentile heat-map, gap vs benchmark |
| 5 | `05_trends.py` | Company search, up to 3 overlaid metrics, YoY % label on every point, CSV download |
| 6 | `06_sectors.py` | Revenue vs ROE bubble chart (size = simulated market cap, colour = sub-sector), sector median KPI bars |
| 7 | `07_capital.py` | Treemap of capital-allocation patterns, drill-down list by pattern |
| 8 | `08_reports.py` | Annual-report links by year; red "Report unavailable" badge for missing years and (with "Verify links") HTTP 404s |
| + | `09_valuation.py`, `10_cashflow.py` | Valuation flags (simulated data) and Cash Flow Intelligence |

`?ticker=XYZ` deep-links the profile page; an unknown ticker shows "Ticker not found - please try another".

### Troubleshooting
* `ImportError: DLL load failed ... Application Control policy has blocked this file` (matplotlib on Windows): matplotlib is **optional**. The dashboard, ETL, analytics, NLP and tests do not need it; PDF reports automatically switch to built-in vector charts. Nothing to fix.
