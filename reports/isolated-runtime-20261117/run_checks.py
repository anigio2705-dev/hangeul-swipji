"""Re-run this owned local review. No models, external DB, deployment or live money.

Install the existing lockfile tools first: npm ci --prefix phase3 --ignore-scripts.
Browser checks remain separately blocked; these commands do not claim UI success.
"""
import json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent/'rerun'
def main():
    OUT.mkdir(exist_ok=True)
    env={k:v for k,v in os.environ.items() if not k.startswith(('HS_','SUPABASE','STRIPE','DATABASE_URL'))}
    commands=[
        [sys.executable,'-m','unittest','discover','-s','phase3','-p','test_*.py','-v'],
        ['node','phase3/test_q002_timezone_ui.cjs'],
        ['node','phase3/postgres-test.cjs'],
        *[['node','scripts/'+name] for name in ['audit-350-lessons.cjs','check-audio-runtime.cjs','check-phase2-pages.cjs','check-foundations.cjs','check-human-audio.cjs','check-week-audio-step1.cjs','check-week-human-audio.cjs','check-week-learning-simulation.cjs']],
        [sys.executable,'reports/isolated-runtime-20261117/check_local_runtime.py']]
    results=[]
    for i,command in enumerate(commands):
        started=time.monotonic();result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=180)
        (OUT/('%02d.log'%i)).write_text(result.stdout+result.stderr)
        results.append({'command':command,'exit':result.returncode,'seconds':round(time.monotonic()-started,3)})
    (OUT/'RESULTS.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results,indent=2))
    return 0 if all(row['exit']==0 for row in results) else 2
if __name__=='__main__':raise SystemExit(main())
