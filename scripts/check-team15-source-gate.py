"""Independent fail-closed regression for the reviewed education-source baseline."""
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
AUDIT=ROOT/'scripts/audit-professional-96.py'
def run():
 return subprocess.run([sys.executable,str(AUDIT)],cwd=ROOT,text=True,capture_output=True)
baseline=run()
if baseline.returncode:
 print(baseline.stdout[-5000:],baseline.stderr[-1000:],file=sys.stderr)
 raise SystemExit('baseline preservation audit failed')
print('PASS approved staging and original source baselines')
for name,expected in (
 ('intro.html','staging source drift: intro.html'),
 ('reading.html','original source or unapproved UI modified: reading.html'),
 ('index.html','original source or unapproved UI modified: index.html'),
):
 path=ROOT/name;original=path.read_bytes()
 try:
  path.write_bytes(original+b'\\n<!-- unauthorized educational source change -->\\n')
  result=run()
  if result.returncode==0 or expected not in result.stdout:
   print(result.stdout[-5000:],result.stderr[-1000:],file=sys.stderr)
   raise SystemExit('FAIL audit did not reject tampered '+name)
  print('PASS rejected unauthorized edit: '+name)
 finally:
  path.write_bytes(original)
if run().returncode:raise SystemExit('FAIL source audit did not recover after test restore')
print('PASS exact-source audit recovers after restoring all test fixtures')
