'use strict';
// Independent P0 regression against the CURRENT Team11 head, not a prior Team15 success.
// Run: node --test tests/team15_latest11_partial_human.test.cjs
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'..','hangul-core.js'),'utf8');
const human={kind:'human',src:'./assets/hangul-audio/human.mp3',sha256:'a'.repeat(64),sourceUrl:'https://example.org/human',author:'Human',license:'CC-BY'};
const held={...human,src:'./assets/hangul-audio/held.mp3',sha256:'b'.repeat(64),disabled:true,holdReason:'human review pending'};
async function setup(){
  const calls={audio:[],tts:[]};
  const context={
    URL,Event:class{},setTimeout,clearTimeout,
    document:{baseURI:'https://example.org/hangul-basics.html',hidden:false,
      addEventListener(){},dispatchEvent(){},querySelectorAll(){return []},querySelector(){return null}},
    window:{addEventListener(){},speechSynthesis:{
      cancel(){},speak(u){calls.tts.push(u.text);queueMicrotask(()=>u.onend?.())}
    },SpeechSynthesisUtterance:class{constructor(word){this.text=word}}},
    fetch:async()=>({ok:true,json:async()=>({recordings:{'가':human,'다':held}})}),
    Audio:class{
      constructor(url){calls.audio.push(url)}
      play(){queueMicrotask(()=>this.onended?.());return Promise.resolve()}
      pause(){}
    }
  };
  vm.runInNewContext(source,context,{filename:'hangul-core.js'});
  await context.window.HSHangul.ready;
  return {h:context.window.HSHangul,calls};
}
test('P0: mixed available + absent sequence plays available human, reports missing (no opt-in)',async()=>{
  const {h,calls}=await setup();
  const result=await h.play(['가','나']);
  assert.equal(calls.audio.length,1,'existing human recording must not be silenced by unrelated missing sound');
  assert.equal(calls.tts.length,0,'synthetic voice must stay off without consent');
  assert.equal(result.status,'partial','partial result must not claim complete human playback');
  assert.deepEqual(Array.from(result.missing),['나']);
  assert.deepEqual(Array.from(result.words),['가']);
});
test('P0: held recording blocks entire sequence even with explicit TTS consent',async()=>{
  const {h,calls}=await setup();
  h.setSyntheticEnabled(true);
  const result=await h.play(['가','다']);
  assert.equal(result.status,'held');
  assert.equal(calls.audio.length,0,'no partial playback can bypass held hard block');
  assert.equal(calls.tts.length,0,'held recording must not be synthesized');
});
test('all missing without consent stays missing, no audio or TTS',async()=>{
  const {h,calls}=await setup();
  const result=await h.play(['나','라']);
  assert.equal(result.status,'missing');
  assert.equal(calls.audio.length,0);
  assert.equal(calls.tts.length,0);
});
test('opted-in mixed sequence still uses human-first and labels synthetic',async()=>{
  const {h,calls}=await setup();
  h.setSyntheticEnabled(true);
  const result=await h.play(['가','나']);
  assert.equal(result.status,'tts-played');
  assert.equal(calls.audio.length,1);
  assert.deepEqual(calls.tts,['나']);
});
