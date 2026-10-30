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

test('P0: a disabled/withdrawn human entry without an audio file must stay held, never become TTS eligible',async()=>{
  const calls={audio:0,tts:0};
  const context={
    URL,Event:class{},setTimeout,clearTimeout,
    document:{baseURI:'https://example.org/hangul-basics.html',hidden:false,
      addEventListener(){},dispatchEvent(){},querySelectorAll(){return []},querySelector(){return null}},
    window:{addEventListener(){},speechSynthesis:{cancel(){},speak(u){calls.tts++;u.onend?.()}},
      SpeechSynthesisUtterance:class{constructor(word){this.text=word}}},
    Audio:class{constructor(){calls.audio++}play(){throw Error('held must never load audio')}pause(){}},
    fetch:async()=>({ok:true,json:async()=>({recordings:{
      '가':human,
      // A withdrawn recording may intentionally omit its old URL/digest.
      '다':{kind:'human',disabled:true,holdReason:'pronunciation review pending'}
    }})})
  };
  vm.runInNewContext(source,context,{filename:'hangul-core.js'});
  const h=context.window.HSHangul;await h.ready;
  h.setSyntheticEnabled(true);
  assert.equal(h.availability('다').state,'held','withdrawn entry must remain a hard review hold');
  assert.equal((await h.play('다')).status,'held','consent cannot override a review hold');
  assert.equal((await h.optionalSynthetic('다')).status,'held','direct TTS API must not bypass hold');
  assert.equal(calls.audio,0);
  assert.equal(calls.tts,0);
});
test('P0: duplicate audio provenance must not turn a disabled recording into missing/TTS-eligible',async()=>{
  const calls={tts:0};
  const context={
    URL,Event:class{},setTimeout,clearTimeout,
    document:{baseURI:'https://example.org/hangul-basics.html',hidden:false,
      addEventListener(){},dispatchEvent(){},querySelectorAll(){return []},querySelector(){return null}},
    window:{addEventListener(){},speechSynthesis:{cancel(){},speak(u){calls.tts++;u.onend?.()}},
      SpeechSynthesisUtterance:class{constructor(word){this.text=word}}},
    Audio:class{constructor(){throw Error('no human audio should be loaded')}pause(){}},
    fetch:async()=>({ok:true,json:async()=>({recordings:{
      '가':human,
      '다':{...human,disabled:true,holdReason:'duplicate source under review'}
    }})})
  };
  vm.runInNewContext(source,context,{filename:'hangul-core.js'});
  const h=context.window.HSHangul;await h.ready;h.setSyntheticEnabled(true);
  assert.equal(h.availability('다').state,'held');
  assert.equal((await h.play('다')).status,'held');
  assert.equal(calls.tts,0);
});
