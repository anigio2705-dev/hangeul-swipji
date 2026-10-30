'use strict';
// Independent Team15 P0: a recording explicitly held for review must not
// be bypassed by optional device TTS, including a mixed playback sequence.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../hangul-core.js'),'utf8');
const human={kind:'human',src:'./assets/hangul-audio/valid.mp3',sourceUrl:'https://example.org/human',author:'Recorded speaker',license:'CC BY-SA 4.0',sha256:'a'.repeat(64)};
let spoken=0,played=0;
const context={
  URL,setTimeout,clearTimeout,Event:class {},
  document:{baseURI:'https://example.org/',hidden:false,addEventListener(){},dispatchEvent(){},querySelectorAll(){return []},querySelector(){return null}},
  window:{addEventListener(){},speechSynthesis:{cancel(){},speak(utterance){spoken++;queueMicrotask(()=>utterance.onend?.())}},SpeechSynthesisUtterance:class{constructor(word){this.text=word}}},
  fetch:async()=>({ok:true,json:async()=>({recordings:{
    '가':human,
    '아':{...human,src:'./assets/hangul-audio/held.mp3',sha256:'b'.repeat(64),disabled:true,holdReason:'human pronunciation pending review'}
  }})}),
  Audio:class{constructor(){played++}pause(){}play(){queueMicrotask(()=>this.onended?.());return Promise.resolve()}}
};
vm.runInNewContext(source,context,{filename:'hangul-core.js'});
(async()=>{
 const h=context.window.HSHangul;
 await h.ready;
 assert.equal(h.availability('아').state,'held','review-held recording must be visible as held');
 assert.equal(h.setSyntheticEnabled(true),true,'test explicitly enables optional TTS');
 const direct=await h.play('아');
 assert.equal(direct.status,'held','opt-in TTS must never bypass a review-held recording');
 assert.equal(spoken,0,'no synthetic utterance for held recording');
 assert.equal(played,0,'no held human file playback');
 const optional=await h.optionalSynthetic('아');
 assert.equal(optional.status,'held','direct optionalSynthetic must respect held inventory');
 assert.equal(spoken,0,'no synthetic utterance through optional API');
 const mixed=await h.play(['가','아']);
 assert.equal(mixed.status,'held','mixed sequence must fail closed when any item is held');
 assert.equal(spoken,0);
 assert.equal(played,0,'must not begin a mixed sequence before held check');
 // With TTS OFF, a missing item must not silence a valid human recording.
 h.setSyntheticEnabled(false);
 const partial=await h.play(['가','녹음없는글자']);
 assert.equal(partial.status,'partial','valid human recordings should play even when another item is missing');
 assert.equal(played,1,'the available human file must play exactly once');
 assert.equal(spoken,0,'partial playback must not silently synthesize');
 const none=await h.play(['녹음없는글자','또없는글자']);
 assert.equal(none.status,'missing','entirely missing sequence remains unavailable');
 assert.equal(played,1);
 h.setSyntheticEnabled(true);
 const missing=await h.play('녹음없는글자');
 assert.equal(missing.status,'tts-played','explicit TTS opt-in remains available for truly missing recordings');
 assert.equal(spoken,1);
 const humanResult=await h.play('가');
 assert.equal(humanResult.status,'played','existing human recordings remain first choice');
 assert.equal(played,2);
 console.log('PASS Team15 held recording blocks opt-in TTS and direct API, mixed sequences fail closed; missing-only opt-in and human recording remain functional.');
})().catch(error=>{console.error(error);process.exitCode=1});
