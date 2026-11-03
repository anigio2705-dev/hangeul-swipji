/* P0 #298: negative regression fixture; expected to FAIL until account ownership is fixed.
 * Run: node --test tests/team12_progress_owner_boundary.test.cjs
 * No network, credentials, or production database.
 */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function harness(initial, uid='learner-B') {
  const state = new Map(Object.entries(initial));
  const calls = [];
  const storage = {
    getItem(k) { return state.has(k) ? state.get(k) : null; },
    setItem(k,v) { state.set(k,String(v)); },
    removeItem(k) { state.delete(k); }
  };
  const context = { console, Set, Array, JSON, Number, Error };
  context.globalThis=context;
  const file=path.resolve(__dirname,'../scripts/team12_server_progress.js');
  vm.runInNewContext(fs.readFileSync(file,'utf8'),context,{filename:file});
  const fetcher=async(url,opts={})=>{
    calls.push({url,opts});
    if(url==='/api/me')return {ok:true,json:async()=>({user:{id:uid}})};
    if(url==='/api/free-progress' && opts.method==='POST')return {ok:true,json:async()=>({ok:true})};
    if(url==='/api/free-progress')return {ok:true,json:async()=>({completed:[]})};
    throw Error('unexpected '+url);
  };
  return {client:context.HSTeam12ServerProgress.client(fetcher,storage,()=>{}),calls,state};
}
test('unowned localStorage must not be silently uploaded to newly authenticated account',async()=>{
  const h=harness({'hs-intro-v1':JSON.stringify({done:{0:true}})});
  assert.equal(await h.client.pull(),true);
  const writes=h.calls.filter(x=>x.url==='/api/free-progress'&&x.opts.method==='POST');
  assert.equal(writes.length,0,'unattributed legacy completion must require explicit ownership/import confirmation');
});
test('localStorage belonging to another account must not be uploaded to current account',async()=>{
  const h=harness({'hs-team12-progress-owner':'learner-A','hs-intro-v1':JSON.stringify({done:{0:true}})});
  assert.equal(await h.client.pull(),true);
  assert.equal(h.calls.filter(x=>x.url==='/api/free-progress'&&x.opts.method==='POST').length,0);
});

test('same owner retains authenticated completion upload',async()=>{
  const h=harness({'hs-team12-progress-owner':'learner-B','hs-intro-v1':JSON.stringify({done:{0:true}})});
  assert.equal(await h.client.pull(),true);
  assert.equal(h.calls.filter(x=>x.url==='/api/free-progress'&&x.opts.method==='POST').length,1);
});
test('unowned progress is quarantined for explicit recovery, not silently discarded',async()=>{
  const raw=JSON.stringify({done:{0:true}});
  const h=harness({'hs-intro-v1':raw});
  assert.equal(await h.client.pull(),true);
  assert.equal(h.state.get('hs-team12-unowned-hs-intro-v1'),raw);
  assert.equal(h.state.get('hs-team12-progress-owner'),'learner-B');
  assert.equal(h.calls.filter(x=>x.url==='/api/free-progress'&&x.opts.method==='POST').length,0);
});
