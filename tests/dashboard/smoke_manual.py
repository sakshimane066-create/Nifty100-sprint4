import sys, glob, os
sys.path.insert(0,'.')
from streamlit.testing.v1 import AppTest
ROOT=os.path.abspath('.'); files=[ROOT+'/src/dashboard/app.py']+sorted(glob.glob(ROOT+'/src/dashboard/pages/*.py'))
bad=0
for f in files:
    at=AppTest.from_file(f, default_timeout=60).run()
    status='OK' if not at.exception else 'EXC'
    if at.exception: bad+=1
    print(f.split('/')[-1], status, [str(e.value)[:200] for e in at.exception], 'errors:',[e.value[:120] for e in at.error])
print('failures',bad)
