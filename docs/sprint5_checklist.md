# Sprint 5 deliverables (spec D-13 .. D-18)
| # | Deliverable | Status | Where |
|---|---|---|---|
| D-13 | cashflow_intelligence.xlsx (+ distress_alerts.csv) | Done | `output/` (`make cashflow`) |
| D-14 | pros_cons_generated.csv - 92 companies, every row confidence > 60% | Done | `output/` (`make nlp`) |
| D-15 | analysis_parsed.csv, cross-validated (cross_validation.csv) | Done | `output/` |
| D-16 | 92 company tearsheets (2 pages, each >= 50 KB) | Done | `reports/tearsheets/` (`make reports`) |
| D-17 | Sector reports | Done - **10**, not 11 (data has 10 sectors) | `reports/sector/` |
| D-18 | Portfolio summary (one page per company) | Done - 92 pages | `reports/portfolio/` |
Also: Module 9.3 business-description tagger (`tag_validation_report.csv`, 87% match vs sectors.xlsx), 9.4 sentiment scores, dashboard page 10 (Cash Flow), profile page shows rule-based pros/cons.
Manual checks left: open 5 random tearsheets (AC-10: no overflow / overlap).
