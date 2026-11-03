import os,subprocess,json,sys,time,sqlite3,hashlib
from pathlib import Path
root=Path(__file__).resolve().parent;logs=root/'evidence';logs.mkdir(exist_ok=True)
env={'PATH':os.environ['PATH'],'LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1','HS_PHASE3_DB':str(root/'isolated.sqlite3')}
result=[]
for phase,mode in [('initial','full'),('restart','restart')]:
 p=subprocess.Popen([sys.executable,str(root/'work_server.py')],cwd=root,env=env,stdout=subprocess.PIPE,stderr=(logs/(phase+'-server.stderr')).open('w'),text=True)
 try:
  ready=json.loads(p.stdout.readline());assert ready['pid']==p.pid
  r=subprocess.run(['node',str(root/'work_http.cjs'),mode,'http://127.0.0.1:'+str(ready['port']),'http://127.0.0.1:'+str(ready['fault_port']),str(logs/(phase+'.json'))],cwd=root,env=env,capture_output=True,text=True,timeout=30)
  (logs/(phase+'.stdout')).write_text(r.stdout);(logs/(phase+'.stderr')).write_text(r.stderr)
  result.append({'phase':phase,'server_pid':p.pid,'ports':ready,'node_exit':r.returncode,'node_result':json.loads((logs/(phase+'.json')).read_text())})
 finally:
  p.terminate();p.wait(timeout=10)
  result[-1]['server_exit']=p.returncode
with sqlite3.connect(root/'isolated.sqlite3') as db:
 snapshot=sqlite3.connect(logs/'isolated.sqlite3');db.backup(snapshot);snapshot.close()
result.append({'db_integrity':sqlite3.connect(logs/'isolated.sqlite3').execute('PRAGMA integrity_check').fetchone()[0]})
(logs/'summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
