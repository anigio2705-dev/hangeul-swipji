'use strict';
// HQ2/12 -> Team15 independent regression: do not label pending inventory as missing.
// Must retain the Team15 fail-closed review-hold and default-off TTS behavior.
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'..','hangul-core.js'),'utf8');
const human={kind:'human',src:'./assets/hangul-audio/human.mp3',sha256:'a'.repeat(64),sourceUrl:'https://example.org/human',author:'Human',license:'CC-BY'};
function setup(){
  let completeFetch;
  const cells=['가','다'].map(sound=>({
    dataset:{sound},classList:{toggle(){}},setAttribute(){},
  }));
  const summary={textContent:''};
  const counts={tts:0,audio:0};
  const context={
    URL,Event:class{},setTimeout,clearTimeout,
    document:{
      baseURI:'https://example.org/hangul-basics.html',hidden:false,
      addEventListener(){},dispatchEvent(){},
      querySelectorAll(selector){return selector==='[data-sound]'?cells:selector==='.board [data-sound]'?cells:[]},
      querySelector(selector){return selector==='[data-board-audio-counts]'?summary:null},
    },
    window:{
      addEventListener(){},
      speechSynthesis:{cancel(){},speak(){counts.tts++}},
      SpeechSynthesisUtterance:class{constructor(text){this.text=text}},
    },
    Audio:class{constructor(){counts.audio++}pause(){}play(){throw Error('not expected')}},
    fetch:()=>new Promise(resolve=>{completeFetch=resolve}),
  };
  vm.runInNewContext(source,context,{filename:'hangul-core.js'});
  return {
    h:context.window.HSHangul,summary,counts,
    resolve:()=>completeFetch({ok:true,json:async()=>({recordings:{
      '가':human,
      // Deliberately missing src/hash: this is a REVIEW HOLD, never TTS-eligible.
      '다':{kind:'human',disabled:true,holdReason:'review pending'},
    }})}),
  };
}
test('pending manifest is labelled loading rather than falsely missing or failed',async()=>{
  const {h,summary,resolve}=setup();
  assert.equal(h.availability('가').state,'loading');
  assert.equal(h.availability('다').state,'loading');
  h.refreshBadges();
  assert.match(summary.textContent,/목록 확인 중 2/);
  assert.equal((await h.play('가')).status,'loading');
  resolve();await h.ready;
  assert.equal(h.availability('가').state,'ready');
  assert.equal(h.availability('다').state,'held');
  assert.equal(h.availability('나').state,'missing');
});
test('loading-state integration never converts withdrawn audio into opted-in TTS',async()=>{
  const {h,resolve,counts}=setup();
  resolve();await h.ready;
  h.setSyntheticEnabled(true);
  assert.equal(h.availability('다').state,'held');
  assert.equal((await h.play('다')).status,'held');
  assert.equal((await h.optionalSynthetic('다')).status,'held');
  assert.equal(counts.tts,0);
  assert.equal(counts.audio,0);
});
