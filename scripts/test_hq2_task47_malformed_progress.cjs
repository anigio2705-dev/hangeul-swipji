'use strict';
// Task #47: malformed successful HTTP payload must not partially switch accounts.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const ctx={window:{}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'team12_server_progress.js'),'utf8'),ctx);
const api=ctx.window.HSTeam12ServerProgress;
const records=new Map();
const storage={
 getItem:k=>records.has(k)?records.get(k):null,
 setItem:(k,v)=>records.set(k,String(v)),
 removeItem:k=>records.delete(k)
};
let user='A', response={completed:[]};
const posted=[];
async function fetcher(url,options={}){
 if(url==='/api/me')return {ok:true,json:async()=>({user:{id:user}})};
 if(url==='/api/free-progress' && options.method==='POST'){
  posted.push({user,body:JSON.parse(options.body)});
  return {ok:true,json:async()=>({ok:true})};
 }
 if(url==='/api/free-progress')return {ok:true,json:async()=>response};
 throw Error('Unexpected URL '+url);
}
(async()=>{
 const ownerKey='hs-team12-progress-owner', key=api.keys[0];
 const old=JSON.stringify({done:{0:true},mistakes:{'1-2':true}});
 storage.setItem(ownerKey,'A');
 storage.setItem(key,old);
 const client=api.client(fetcher,storage);
 assert.equal(await client.pull(),true);
 user='B';
 for(const malformed of [
  {completed:[null]},
  {completed:[7]},
  {completed:[{stage:1,lesson:'not-a-number'}]}
 ]){
  response=malformed;
  assert.equal(await client.pull(),false,'malformed progress must fail closed');
  assert.equal(storage.getItem(ownerKey),'A','failed read must preserve old owner');
  assert.equal(storage.getItem(key),old,'failed read must preserve old progress');
  assert.equal(storage.getItem('hs-team12-account-A-'+key),null,'failed read must not back up or switch');
  assert.equal(posted.filter(p=>p.user==='B').length,0,'must not upload A progress to B');
 }
 response={completed:[]};
 assert.equal(await client.pull(),true,'valid retry must work');
 assert.equal(storage.getItem(ownerKey),'B');
 assert.equal(storage.getItem(key),null);
 assert.equal(storage.getItem('hs-team12-account-A-'+key),old);
 console.log('Task #47 malformed progress payload atomicity PASS');
})().catch(e=>{console.error(e);process.exitCode=1});
