"""Exact-source localhost process restart and static delivery. No external API."""
import hashlib,http.client,json,os,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
def main():
    with tempfile.TemporaryDirectory(prefix='hs-isolated-process-') as temporary:
        env={k:v for k,v in os.environ.items() if not k.startswith(('HS_','SUPABASE','STRIPE','DATABASE_URL'))}
        env['HS_PHASE3_DB']=str(Path(temporary)/'test.sqlite3')
        import socket
        with socket.socket() as listener:listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
        def call(path,data=None,cookie=''):
            connection=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
            connection.request('POST' if data is not None else 'GET',path,None if data is None else json.dumps(data),{'Content-Type':'application/json','Cookie':cookie})
            result=connection.getresponse();body=result.read();headers=dict(result.getheaders());status=result.status;connection.close()
            return status,body,headers
        log=(OUT/'runtime-server.log').open('w')
        def launch():
            child=subprocess.Popen([sys.executable,'phase3/server.py','--port',str(port)],cwd=ROOT,env=env,stdout=log,stderr=log)
            for _ in range(100):
                try:
                    if call('/')[0]==200:return child
                except OSError:pass
                if child.poll() is not None:raise RuntimeError('SERVER_EXITED')
                time.sleep(.05)
            child.terminate();child.wait();raise RuntimeError('SERVER_NOT_READY')
        child=launch();first_pid=child.pid;results=[]
        try:
            for page in sorted(ROOT.glob('*.html')):
                status,body,headers=call('/'+page.name)
                results.append({'path':page.name,'status':status,'same_source_bytes':body==page.read_bytes(),'redirect':headers.get('Location')})
            status,body,headers=call('/api/register',{'email':'persist@example.test','password':'Only-Test-Password-12345!','nickname':'Saved learner','role':'learner','adultConsent':True})
            assert status==200,(status,body)
            cookie=headers['Set-Cookie'].split(';')[0]
            status,body,_=call('/api/learning/placement',{'groups':[2,3,1,0]},cookie);assert status==200,(status,body)
            before=json.loads(call('/api/learning',cookie=cookie)[1])
            # Controlled process termination, same disposable database; not a disk-loss test.
            child.terminate();child.wait(timeout=10);exit_code=child.returncode
            child=launch();second_pid=child.pid
            status,body,_=call('/api/learning',cookie=cookie);assert status==200,(status,body)
            after=json.loads(body);assert before['placement']==after['placement']
            status,body,_=call('/api/me',cookie=cookie);assert status==200 and json.loads(body)['user']['nickname']=='Saved learner'
            restart={'first_pid':first_pid,'exit_code':exit_code,'second_pid':second_pid,'different_pid':first_pid!=second_pid,'placement_preserved':before['placement']==after['placement'],'session_preserved':True,'profile_preserved':True,'real_process_restart':True,'production_data':False}
            (OUT/'http-runtime.json').write_text(json.dumps({'pages':results,'restart':restart},indent=2)+'\n')
            print(json.dumps({'page_count':len(results),'same_bytes':sum(x['same_source_bytes'] for x in results),'non_identical':[x for x in results if not x['same_source_bytes']],'restart':restart},indent=2))
        finally:
            child.terminate();child.wait(timeout=10);log.close()
if __name__=='__main__':main()
