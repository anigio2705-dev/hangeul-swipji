'use strict';
// Read-only #59 candidate: exercise the real shared audio engine in a disposable VM.
// No microphone, browser, network, production DB, synthetic speech or real audio files.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const core=fs.readFileSync(path.join(__dirname,'..','hangul-core.js'),'utf8');
const human=(word,disabled=false)=>({
  kind:'human',src:'./assets/hangul-audio/'+word+'.mp3',sha256:'a'.repeat(64),
  sourceUrl:'https://example.test/source',author:'Review fixture',license:'fixture-only',
  ...(disabled?{disabled:true,holdReason:'검수 보류'}:{})
});
function harness(initial,failFirst=false){
  let manifest=initial,requests=0,audioCreated=0,synthSpoken=0,lastUrl='';
  const statusNode={textContent:''};
  const document={
    baseURI:'https://example.test/hangul-board.html',
    addEventListener(){},dispatchEvent(){},
    querySelectorAll(selector){return selector==='[data-audio-status]'?[statusNode]:[]},
    querySelector(){return null},
    createElement(){return {dataset:{},classList:{toggle(){}},setAttribute(){}}}
  };
  const window={
    addEventListener(){},
    speechSynthesis:{cancel(){},speak(){synthSpoken++}}
  };
  class FakeAudio{
    constructor(url){audioCreated++;lastUrl=url}
    pause(){}
    play(){queueMicrotask(()=>this.onended?.());return Promise.resolve()}
  }
  const fetch=async()=>{
    requests++;
    if(failFirst&&requests===1)throw Error('network unavailable');
    return {ok:true,json:async()=>manifest};
  };
  vm.runInNewContext(core,{
    window,document,fetch,Audio:FakeAudio,URL,Promise,
    Event:class{constructor(type){this.type=type}}
    // No setTimeout: deterministic tests do not wait for a 15-second audio timeout.
  },{filename:'hangul-core.js',timeout:2000});
  return {H:window.HSHangul,setManifest:x=>{manifest=x},stats:()=>({
    requests,audioCreated,synthSpoken,status:statusNode.textContent,lastUrl
  })};
}
test('#59 missing recording is explicit and provides a non-synthetic learning alternative',async()=>{
  const x=harness({recordings:{}});
  await x.H.ready;
  const result=await x.H.play('가');
  assert.equal(result.status,'missing');
  assert.equal(x.H.availability('가').state,'missing');
  assert.match(x.stats().status,/가.*선생님과 함께 읽어 주세요/);
  assert.equal(x.stats().audioCreated,0);
  assert.equal(x.stats().synthSpoken,0);
});
test('#59 held human recording is not played or silently synthesized',async()=>{
  const x=harness({recordings:{'가':human('ga',true)}});
  await x.H.ready;
  assert.equal(x.H.availability('가').state,'held');
  const result=await x.H.play('가');
  assert.equal(result.status,'held');
  assert.match(x.stats().status,/재생 보류/);
  assert.equal(x.stats().audioCreated,0);
  assert.equal(x.stats().synthSpoken,0);
});
test('#59 failed manifest fetch can be retried and newly reviewed recording played',async()=>{
  const x=harness({recordings:{}},true);
  await x.H.ready;
  assert.equal(x.H.availability('가').state,'unavailable');
  const retry=await x.H.reloadManifest();
  assert.equal(retry.status,'ready');
  assert.equal(x.H.availability('가').state,'missing');
  x.setManifest({recordings:{'가':human('ga')}});
  const refreshed=await x.H.reloadManifest();
  assert.equal(refreshed.status,'ready');
  assert.equal(x.H.availability('가').state,'ready');
  const result=await x.H.play('가');
  assert.equal(result.status,'played');
  assert.equal(x.stats().audioCreated,1);
  assert.equal(x.stats().synthSpoken,0);
  assert.match(x.stats().lastUrl,/\/assets\/hangul-audio\/ga\.mp3\?v=aaaaaaaaaaaaaaaa/);
});
