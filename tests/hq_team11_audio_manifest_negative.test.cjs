/* Independent HQ/15-team negative QA of Team11's audio fix.
 * Tests the real hangul-core.js in a VM. No external audio, network, or TTS.
 */
'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'..','hangul-core.js'),'utf8');
function boot(payload){
  let audioCalls=0;
  const document={
    baseURI:'https://example.test/hangul-basics.html',
    addEventListener(){},dispatchEvent(){},querySelectorAll(){return []},
    querySelector(){return null}
  };
  const window={addEventListener(){},speechSynthesis:{cancel(){}}};
  class ForbiddenAudio{constructor(){audioCalls++;throw Error('Unexpected audio playback')}}
  const ctx={document,window,Audio:ForbiddenAudio,Event:class{},URL,setTimeout,clearTimeout,
    fetch:async()=>({ok:true,json:async()=>payload})};
  vm.runInNewContext(source,ctx);
  return {core:window.HSHangul,audioCalls:()=>audioCalls};
}
test('invalid manifest fails closed and cannot pretend to play a recording',async()=>{
  const {core,audioCalls}=boot({recordings:[]});
  await core.ready;
  const outcome=await core.play('가');
  assert.equal(outcome.status,'manifest-error');
  assert.equal(audioCalls(),0);
});
test('held human recording cannot be played or represented as available',async()=>{
  const {core,audioCalls}=boot({recordings:{'가':{
    kind:'human',src:'./assets/hangul-audio/ac00-r2.mp3',
    sha256:'b'.repeat(64),sourceUrl:'https://commons.wikimedia.org/wiki/File:Ko.mp3',
    author:'human speaker',license:'CC-BY',disabled:true,holdReason:'listening QA pending'
  }}});
  await core.ready;
  assert.equal(core.availability('가').state,'held');
  const outcome=await core.play('가');
  assert.equal(outcome.status,'held');
  assert.equal(audioCalls(),0);
});
