"""Verify deployed bytes, without equating delivery/decoding to listening approval."""
import concurrent.futures
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
manifest=json.loads((ROOT/'hangul-audio-manifest.json').read_text())
files=['intro.html','beginner1.html','beginner2.html','intermediate1.html','intermediate2.html','advanced1.html','advanced2.html','hangul-basics.html','hangul-week.html','reading.html','reading-curriculum.js','reading-alternates.js','hangul-core.js','site-language.js','hangul-audio-manifest.json']+[r['src'].removeprefix('./') for r in manifest['recordings'].values()]
def verify(file):
    url='https://anigio2705-dev.github.io/hangeul-swipji/'+file+'?release='+commit
    expected=hashlib.sha256((ROOT/file).read_bytes()).hexdigest()
    try:
        with urllib.request.urlopen(url,timeout=30) as response:
            body=response.read();actual=hashlib.sha256(body).hexdigest()
            return {'path':file,'status':response.status,'bytes':len(body),'sha256':actual,'matchesLocal':expected==actual}
    except Exception as error:return {'path':file,'error':str(error),'matchesLocal':False}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(verify,files))
report={'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'codeCommit':commit,'scope':'Actual GitHub Pages HTTP responses and exact SHA256 correspondence; not a listening approval','files':len(results),'audioFiles':len(manifest['recordings']),'passed':all(r['matchesLocal'] for r in results),'results':results}
(ROOT/'audit/live-delivery.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='results'}))
raise SystemExit(0 if report['passed'] else 1)
