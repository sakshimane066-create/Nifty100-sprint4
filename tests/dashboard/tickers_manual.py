"""Run Company Profile / Trends / Documents for several tickers incl. edge cases (SBIN no BS, JIOFIN short history)."""
import os, sys
sys.path.insert(0, os.path.abspath('.'))
from streamlit.testing.v1 import AppTest
R = os.path.abspath('.')
bad = 0
for page in ['02_profile', '05_trends', '08_documents']:
    for t in ['TCS', 'SBIN', 'JIOFIN', 'LICI', 'HDFCBANK', 'ATGL', 'M&M', 'BAJAJ-AUTO', 'ADANIGREEN', 'ZOMATO']:
        at = AppTest.from_file(f'{R}/src/dashboard/pages/{page}.py', default_timeout=60)
        at.session_state['ticker'] = t
        at.run()
        if at.exception:
            bad += 1; print(page, t, 'EXC', str(at.exception[0].value)[:200])
print('ticker failures', bad)
