const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const mode=process.argv[2],base=process.argv[3],faultBase=process.argv[4],output=process.argv[5];
assert.equal(new URL(base).hostname,'127.0.0.1');
const log=[],checks=[];const password='Offline-Work298-Only';
const users={};
function jar(){return {cookie:''}}
async function api(j,path,method='GET',data,headers={}){
 const r=await fetch(base+path,{method,headers:{'Content-Type':'application/json',...(j.cookie?{Cookie:j.cookie}:{}),...headers},body:data===undefined?undefined:JSON.stringify(data)});
 const set=r.headers.get('set-cookie');if(set)j.cookie=set.split(';')[0];
 const body=await r.json();log.push({path,method,status:r.status});return {status:r.status,body};
}
function instance(j,initial={},fault){
 const values=new Map(Object.entries(initial)),context={console,Set,Array,JSON,Number,Error,AbortController};context.globalThis=context;
 vm.runInNewContext(fs.readFileSync('scripts/team12_server_progress.js','utf8'),context);
 const fetcher=async(path,opts={})=>{
  if(fault&&path==='/api/free-progress'&&opts.method!=='POST'){
   try{const r=await fetch(faultBase+'/'+fault);log.push({path,method:'GET',status:r.status,injected:true});return r}
   catch(e){log.push({path,method:'GET',network_error:true,injected:true});throw e}
  }
  const r=await fetch(base+path,{...opts,headers:{...(opts.headers||{}),Cookie:j.cookie}});
  log.push({path,method:opts.method||'GET',status:r.status,client:true});return r;
 };
 return {values,client:context.HSTeam12ServerProgress.client(fetcher,{getItem:k=>values.has(k)?values.get(k):null,setItem:(k,v)=>values.set(k,String(v)),removeItem:k=>values.delete(k)},()=>{})};
}
function check(name,ok,detail={}){checks.push({name,status:ok?'PASS':'FAIL',...detail})}
async function main(){
 if(mode==='race'){
  const j=jar();const a=(await api(j,'/api/login','POST',{email:'work-a@example.test',password})).body.user;
  let resume,started;const gate=new Promise(r=>resume=r),seen=new Promise(r=>started=r);let blocked=false;
  const values=new Map([['hs-team12-progress-owner',a.id],['hs-intro-v1','{"done":{"10":true,"11":true}}']]);
  const c={Set,Array,JSON,Number,Error,AbortController};c.globalThis=c;vm.runInNewContext(fs.readFileSync('scripts/team12_server_progress.js','utf8'),c);
  const f=async(path,opts={})=>{const cookie=j.cookie;if(opts.method==='POST'&&JSON.parse(opts.body).lesson===11&&!blocked){blocked=true;started();await gate;}const r=await fetch(base+path,{...opts,headers:{...(opts.headers||{}),Cookie:cookie}});log.push({path,method:opts.method||'GET',status:r.status,session_captured_before_delay:true});return r;};
  const client=c.HSTeam12ServerProgress.client(f,{getItem:k=>values.has(k)?values.get(k):null,setItem:(k,v)=>values.set(k,String(v)),removeItem:k=>values.delete(k)},()=>{});
  const first=client.pull();await seen;
  await api(j,'/api/login','POST',{email:'work-b@example.test',password});await client.pull();
  values.set('hs-intro-v1','{"done":{"10":true}}');client.changed('hs-intro-v1',values.get('hs-intro-v1'));
  resume();await first;await client.flush();
  for(let i=0;i<100;i++){if(client.pending.size===0)break;await new Promise(r=>setTimeout(r,10));}
  const bProgress=await api(j,'/api/free-progress');
  check('inflight_A_response_does_not_drop_B_same_lesson_pending',bProgress.body.completed.some(x=>x.lesson===11),{B_local_done11:true,B_server_done11:bProgress.body.completed.some(x=>x.lesson===11),pending_count:client.pending.size});
  const aj=jar();await api(aj,'/api/login','POST',{email:'work-a@example.test',password});
  check('old_request_captured_A_or_aborted_no_B_mix', (await api(aj,'/api/free-progress')).body.completed.some(x=>x.lesson===11) || checks[0].status==='PASS');
 }else if(mode==='restart'){
  const j=jar();let r=await api(j,'/api/login','POST',{email:'work-b@example.test',password});assert.equal(r.status,200);
  for(let i=0;i<2;i++)assert.equal((await api(j,'/api/free-progress','POST',{stage:1,lesson:2})).status,200);
  r=await api(j,'/api/free-progress');check('new_server_process_restore_and_duplicate0',r.body.completed.length===1&&r.body.completed[0].lesson===2,{count:r.body.completed.length});
 }else{
  for(const [name,role] of [['a','learner'],['b','learner'],['teacher','teacher']]){const j=jar(),r=await api(j,'/api/register','POST',{email:`work-${name}@example.test`,password,nickname:'Work '+name,role,adultConsent:true});assert.equal(r.status,200);users[name]={j,id:r.body.user.id};}
  const A=users.a,B=users.b;
  const h=instance(A.j,{'hs-team12-progress-owner':A.id,'hs-intro-v1':'{"done":{"0":true}}'});assert.equal(await h.client.pull(),true);
  let r=await api(A.j,'/api/free-progress');check('same_owner_actual_http_upload',r.body.completed.some(x=>x.lesson===1));
  const shared=instance(B.j,Object.fromEntries(h.values));assert.equal(await shared.client.pull(),true);
  r=await api(B.j,'/api/free-progress');check('account_switch_no_A_progress_in_B',r.body.completed.length===0);
  shared.values.set('hs-intro-v1','{"done":{"1":true}}');shared.client.changed('hs-intro-v1',shared.values.get('hs-intro-v1'));
  for(let i=0;i<30;i++){await new Promise(r=>setTimeout(r,10));r=await api(B.j,'/api/free-progress');if(r.body.completed.some(x=>x.lesson===2))break;}
  check('B_actual_http_save',r.body.completed.some(x=>x.lesson===2));
  assert.equal((await api(B.j,'/api/logout','POST',{})).status,200);check('logout_rejects_get401',(await api(B.j,'/api/free-progress')).status===401);
  assert.equal((await api(B.j,'/api/login','POST',{email:'work-b@example.test',password})).status,200);
  const fresh=instance(B.j);assert.equal(await fresh.client.pull(),true);check('relogin_new_storage_restores_progress',JSON.parse(fresh.values.get('hs-intro-v1')).done['1']===true);
  const other=jar();assert.equal((await api(other,'/api/login','POST',{email:'work-b@example.test',password})).status,200);
  check('independent_login_session_restores',(await api(other,'/api/free-progress')).body.completed.some(x=>x.lesson===2));
  check('nonlearner_get403',(await api(users.teacher.j,'/api/free-progress')).status===403);
  check('cross_origin_post403',(await api(B.j,'/api/free-progress','POST',{stage:1,lesson:50},{Origin:'https://untrusted.example'})).status===403);
  check('anonymous_get401',(await api(jar(),'/api/free-progress')).status===401);
  for(const fault of ['401','403','500','503','disconnect']){
   const f=instance(B.j,{'hs-team12-progress-owner':A.id,'hs-intro-v1':'{"done":{"0":true}}'},fault);
   const result=await f.client.pull();check('owner_not_committed_on_GET_'+fault,result===false&&f.values.get('hs-team12-progress-owner')===A.id,{returned:result,owner_is_B:f.values.get('hs-team12-progress-owner')===B.id,archive_preserved:f.values.has('hs-team12-account-'+A.id+'-hs-intro-v1')});
   const recovered=instance(B.j,Object.fromEntries(f.values));check('recovery_after_'+fault,await recovered.client.pull());
  }
 }
 const result={mode,node:process.version,pid:process.pid,scope:'exact_client_VM_with_real_loopback_HTTP_NOT_browser_UI',client_sha:'1a137c569ce8f39277d3d9f07e95b72c1cf3820e',server_sha:'a2abc3c08ec0c4d245ae0be0670a1b47148f2e00',checks,http_log:log,passed:checks.filter(x=>x.status==='PASS').length,failed:checks.filter(x=>x.status==='FAIL').length};fs.writeFileSync(output,JSON.stringify(result,null,2));console.log(JSON.stringify(result));return result.failed?2:0;
}
main().then(c=>process.exitCode=c).catch(e=>{console.error(e);process.exitCode=1});
