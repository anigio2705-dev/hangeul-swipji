/* P0 #298: account ownership and failed-sync regression tests.
 * node --test tests/team12_progress_owner_boundary.test.cjs
 */
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
function harness(initial, options={}){
 const state=new Map(Object.entries(initial));const calls=[];let uid=options.uid||'learner-B';
 const storage={getItem(k){return state.has(k)?state.get(k):null},setItem(k,v){state.set(k,String(v))},removeItem(k){state.delete(k)}};
 const context={console,Set,Array,JSON,Number,Error,AbortController};context.globalThis=context;
 const file=path.resolve(__dirname,'../scripts/team12_server_progress.js');
 vm.runInNewContext(fs.readFileSync(file,'utf8'),context,{filename:file});
 const fetcher=async(url,opts={})=>{calls.push({url,opts,uid});if(options.fetcher)return options.fetcher(url,opts,uid);
  if(url==='/api/me')return {ok:true,json:async()=>({user:{id:uid}})};
  if(url==='/api/free-progress'&&opts.method==='POST')return {ok:true,json:async()=>({ok:true})};
  if(url==='/api/free-progress')return {ok:true,json:async()=>({completed:[]})};
  throw Error('unexpected '+url);
 };
 return {client:context.HSTeam12ServerProgress.client(fetcher,storage,()=>{}),calls,state,setUid(v){uid=v}};
}
function posts(h){return h.calls.filter(x=>x.url==='/api/free-progress'&&x.opts.method==='POST')}
test('unowned progress must never upload to newly authenticated account',async()=>{
 const h=harness({'hs-intro-v1':JSON.stringify({done:{0:true}})});
 assert.equal(await h.client.pull(),true);assert.equal(posts(h).length,0);
});
test('another owner progress must not upload to current account',async()=>{
 const h=harness({'hs-team12-progress-owner':'learner-A','hs-intro-v1':JSON.stringify({done:{0:true}})});
 assert.equal(await h.client.pull(),true);assert.equal(posts(h).length,0);
});
test('same owner retains authenticated upload',async()=>{
 const h=harness({'hs-team12-progress-owner':'learner-B','hs-intro-v1':JSON.stringify({done:{0:true}})});
 assert.equal(await h.client.pull(),true);assert.equal(posts(h).length,1);
});
test('unowned progress archived without deleting original backup',async()=>{
 const raw=JSON.stringify({done:{0:true}}),h=harness({'hs-intro-v1':raw});
 assert.equal(await h.client.pull(),true);
 assert.equal(h.state.get('hs-team12-unowned-hs-intro-v1'),raw);
 assert.equal(h.state.get('hs-team12-progress-owner'),'learner-B');assert.equal(posts(h).length,0);
});
test('GET 503 must not change owner or clear active storage',async()=>{
 const raw=JSON.stringify({done:{0:true}});const h=harness({'hs-team12-progress-owner':'learner-A','hs-intro-v1':raw},{fetcher:async(url)=>{
  if(url==='/api/me')return {ok:true,json:async()=>({user:{id:'learner-B'}})};
  return {ok:false,status:503,json:async()=>({})};
 }});
 assert.equal(await h.client.pull(),false);
 assert.equal(h.state.get('hs-team12-progress-owner'),'learner-A');
 assert.equal(h.state.get('hs-intro-v1'),raw);assert.equal(posts(h).length,0);
});
test('GET 401 keeps previously stored progress and does not POST',async()=>{
 const raw=JSON.stringify({done:{0:true}});const h=harness({'hs-team12-progress-owner':'learner-A','hs-intro-v1':raw},{fetcher:async()=>({ok:false,status:401,json:async()=>({})})});
 assert.equal(await h.client.pull(),false);assert.equal(h.state.get('hs-team12-progress-owner'),'learner-A');assert.equal(h.state.get('hs-intro-v1'),raw);assert.equal(posts(h).length,0);
});
test('switching owner aborts in-flight POST and does not post stored A progress as B',async()=>{
 const raw=JSON.stringify({done:{0:true}});let resolveOldPost;
 const h=harness({'hs-team12-progress-owner':'learner-A','hs-intro-v1':raw},{uid:'learner-A',fetcher:async(url,opts,uid)=>{
  if(url==='/api/me')return {ok:true,json:async()=>({user:{id:uid}})};
  if(url==='/api/free-progress'&&!opts.method)return {ok:true,json:async()=>({completed:[]})};
  if(url==='/api/free-progress'&&opts.method==='POST')return new Promise(resolve=>{resolveOldPost=resolve});
  throw Error('unexpected '+url);
 }});
 const oldPull=h.client.pull();
 for(let i=0;i<20&&!resolveOldPost;i++)await Promise.resolve();
 assert.equal(typeof resolveOldPost,'function');assert.equal(posts(h).length,1);
 h.setUid('learner-B');
 const newPull=h.client.pull();
 resolveOldPost({ok:true,json:async()=>({ok:true})});
 await oldPull;assert.equal(await newPull,true);
 assert.equal(h.state.get('hs-team12-progress-owner'),'learner-B');
 assert.equal(h.state.get('hs-team12-account-learner-A-hs-intro-v1'),raw);
 assert.equal(posts(h).filter(x=>x.uid==='learner-B').length,0);
});
