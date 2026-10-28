'use strict';
const assert=require('node:assert/strict');const fs=require('node:fs');const vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'team12_server_progress.js'),'utf8');
const ctx={window:{}};vm.runInNewContext(source,ctx);const api=ctx.window.HSTeam12ServerProgress;
const store=new Map();const storage={getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v),removeItem:k=>store.delete(k)};
let uid='student-A';const records=new Map([['student-A',[]],['student-B',[{stage:2,lesson:4}]]]);let fail=false;
async function fetcher(path,opt={}){if(fail)throw Error('offline');if(path==='/api/me')return {ok:true,json:async()=>({user:{id:uid}})};if(path==='/api/free-progress'){if(opt.method==='POST'){const row=JSON.parse(opt.body);const list=records.get(uid);if(!list.some(x=>x.stage===row.stage&&x.lesson===row.lesson))list.push(row);return {ok:true,json:async()=>({ok:true})}}return {ok:true,json:async()=>({completed:records.get(uid)})}}throw Error(path)}
(async()=>{const c=api.client(fetcher,storage);assert.equal(await c.pull(),true);const k=api.keys[0];const saved=JSON.stringify({done:{0:true},mistakes:{'1-2':true}});storage.setItem(k,saved);c.changed(k,saved);await c.flush();assert.equal(records.get('student-A').length,1);assert.equal(records.get('student-A')[0].lesson,1);assert.equal(await c.pull(),true);assert.equal(JSON.parse(storage.getItem(k)).mistakes['1-2'],true);
uid='student-B';assert.equal(await c.pull(),true);assert.equal(storage.getItem(k),null,'other user must not inherit first student progress');assert.ok(storage.getItem('hs-team12-account-student-A-'+k),'previous account must retain a backup');assert.equal(JSON.parse(storage.getItem(api.keys[1])).done[3],true);assert.equal(records.get('student-B').length,1);
const second=api.client(fetcher,storage);assert.equal(await second.pull(),true);assert.equal(records.get('student-B').length,1);fail=true;assert.equal(await c.pull(),false);assert.equal(JSON.parse(storage.getItem(api.keys[1])).done[3],true,'offline must not delete local record');assert.equal(api.completed(JSON.stringify({done:{0:true,49:true,50:true}})).length,2,'only lessons 1–50 are valid');
let release;let blocked=false;const slowFetch=async(path,opt={})=>{if(path==='/api/free-progress'&&opt.method==='POST'&&!blocked){blocked=true;await new Promise(resolve=>{release=resolve})}return fetcher(path,opt)};
fail=false;const late=api.client(slowFetch,storage);assert.equal(await late.pull(),true);const k2=api.keys[1];late.changed(k2,JSON.stringify({done:{4:true}}));for(let i=0;i<20&&!release;i++)await Promise.resolve();assert.equal(typeof release,'function');late.changed(k2,JSON.stringify({done:{4:true,5:true}}));release();for(let i=0;i<30;i++)await Promise.resolve();assert.ok(records.get('student-B').some(x=>x.stage===2&&x.lesson===6),'completion added during pending HTTP request must be flushed');
// Returning to an account must restore its own local-only records without
// leaking the other account's completed lessons to the authenticated API.
for(let i=0;i<100&&late.pending.size;i++)await new Promise(resolve=>setImmediate(resolve));
assert.equal(late.pending.size,0,'all in-flight student B progress requests must settle before switching accounts');
storage.setItem(k2,JSON.stringify({done:{3:true,4:true,5:true}}));
const stale=api.client(fetcher,storage);
assert.equal(await stale.pull(),true,'stale client begins on student B');
uid='student-A';
assert.equal(await c.pull(),true);
assert.equal(JSON.parse(storage.getItem(k)).done[0],true,'student A progress restored from its account backup');
assert.equal(storage.getItem(api.keys[1]),null,'student B progress must not appear in student A');
const beforeA=records.get('student-A').length;
stale.changed(api.keys[1],JSON.stringify({done:{12:true}}));
await stale.flush();
assert.equal(records.get('student-A').length,beforeA,'stale client cannot upload another account progress');
uid='student-B';
assert.equal(await c.pull(),true);
assert.equal(JSON.parse(storage.getItem(api.keys[1])).done[3],true,'student B local progress restored');
assert.equal(JSON.parse(storage.getItem(api.keys[1])).done[5],true,'student B offline completion retained');
console.log('team12 server progress integration tests passed');})().catch(e=>{console.error(e);process.exitCode=1});
