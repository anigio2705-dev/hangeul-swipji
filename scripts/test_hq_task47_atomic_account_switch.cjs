'use strict';
// Task #47: a failed server read must not partially switch the local progress owner.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ctx = {window:{}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'team12_server_progress.js'),'utf8'),ctx);
const api=ctx.window.HSTeam12ServerProgress;
const state=new Map();
const storage={
  getItem:k=>state.has(k)?state.get(k):null,
  setItem:(k,v)=>state.set(k,String(v)),
  removeItem:k=>state.delete(k)
};
let user='A', failProgress=false;
const sent=[];
async function fetcher(url,options={}){
  if(url==='/api/me')return {ok:true,json:async()=>({user:{id:user}})};
  if(url==='/api/free-progress'&&options.method==='POST'){
    sent.push({user,body:JSON.parse(options.body)});
    return {ok:true,json:async()=>({ok:true})};
  }
  if(url==='/api/free-progress'){
    if(failProgress)throw Error('simulated free-progress timeout');
    return {ok:true,json:async()=>({completed:[]})};
  }
  throw Error('unexpected '+url);
}
(async()=>{
  const key=api.keys[0],ownerKey='hs-team12-progress-owner';
  const own=JSON.stringify({done:{0:true},mistakes:{'1-2':true}});
  storage.setItem(ownerKey,'A');
  storage.setItem(key,own);
  const client=api.client(fetcher,storage);
  assert.equal(await client.pull(),true);
  assert.equal(storage.getItem(ownerKey),'A');
  user='B';failProgress=true;
  assert.equal(await client.pull(),false,'failed fetch must report failure');
  assert.equal(storage.getItem(ownerKey),'A','failed server read must not commit an owner change');
  assert.equal(storage.getItem(key),own,'failed server read must preserve prior owner local state');
  assert.equal(storage.getItem('hs-team12-account-A-'+key),null,'failed read must not create an account backup');
  failProgress=false;
  assert.equal(await client.pull(),true,'retry must succeed');
  assert.equal(storage.getItem(ownerKey),'B');
  assert.equal(storage.getItem(key),null,'B must not inherit A completed lessons');
  assert.equal(storage.getItem('hs-team12-account-A-'+key),own,'A backup must be retained on successful switch');
  assert.equal(sent.some(x=>x.user==='B'&&x.body.stage===1&&x.body.lesson===1),false,'A completion must not upload to B');
  console.log('Task #47 atomic account switch and retry PASS');
})().catch(e=>{console.error(e);process.exitCode=1});
