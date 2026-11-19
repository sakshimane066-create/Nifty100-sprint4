PY ?= python3
.PHONY: pipeline all load ratios peers valuation nlp cashflow reports test dashboard clean
pipeline:   ## one command: ETL -> ratios -> peers -> valuation -> nlp -> cashflow
	$(PY) -m src.pipeline
all: load ratios peers valuation nlp cashflow reports
load:       ## ETL: 12 Excel files -> data/nifty100.db (+ output/load_audit.csv, validation_failures.csv)
	$(PY) -m src.etl.loader
ratios:     ## Ratio engine -> financial_ratios table, capital_allocation.csv, ratio_edge_cases.log
	$(PY) -m src.analytics.ratios
peers:      ## Peer percentiles + best-in-class / watch-list flags
	$(PY) -m src.analytics.peer
valuation:  ## output/valuation_summary.xlsx + valuation_flags.csv
	$(PY) -m src.analytics.valuation
nlp:        ## analysis_parsed.csv, cross_validation.csv, pros_cons_generated.csv, tag_validation_report.csv
	$(PY) -m src.nlp.run
cashflow:   ## cashflow_intelligence.xlsx + distress_alerts.csv
	$(PY) -m src.analytics.cashflow_intel
reports:    ## 92 tearsheets + sector reports + portfolio summary -> reports/
	$(PY) -m src.reports.run
test:
	$(PY) -m pytest --cov=src --cov-report=term-missing
dashboard:
	streamlit run src/dashboard/app.py
clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} + ; rm -rf .pytest_cache .coverage
