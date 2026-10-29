'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'..','hangul-core.js'),'utf8');
test('team12 audio script parses without duplicate lexical declarations',()=>{
  assert.doesNotThrow(()=>new vm.Script(source,{filename:'hangul-core.js'}));
});
const ga={kind:'human',src:'./assets/hangul-audio/ga.mp3',sourceUrl:'https://example.test/ga',author:'reviewed',license:'reviewed'};
function boot({recordings={},failed=false,speech=true}={}){
  const sounds=[];
  class Utterance{constructor(word){this.text=word}}
  const synth={cancel(){},speak(utterance){sounds.push(utterance.text);queueMicrotask(()=>utterance.onend?.())}};
  class MockAudio{play(){queueMicrotask(()=>this.onended?.());return Promise.resolve()}pause(){}}
  const document={baseURI:'https://example.test/',hidden:false,querySelectorAll(){return []},querySelector(){return null},addEventListener(){},dispatchEvent(){}};
  const window={speechSynthesis:speech?synth:null,SpeechSynthesisUtterance:speech?Utterance:undefined,addEventListener(){}};
  vm.runInNewContext(source,{window,document,Audio:MockAudio,URL,SpeechSynthesisUtterance:Utterance,Event:class{constructor(type){this.type=type}},fetch:async()=>({ok:!failed,json:async()=>({recordings})})});
  return {H:window.HSHangul,sounds};
}
test('TTS is OFF by default, and unsupported browsers cannot opt in',async()=>{
  const {H,sounds}=boot();await H.ready;
  assert.equal((await H.optionalSynthetic('나')).status,'tts-disabled');
  assert.deepEqual(sounds,[]);
  const unsupported=boot({speech:false});await unsupported.H.ready;
  assert.equal(unsupported.H.setSyntheticEnabled(true),false);
});
test('held human recording stays blocked even after explicit TTS opt-in',async()=>{
  const {H,sounds}=boot({recordings:{'나':{...ga,disabled:true,holdReason:'교사 검수 보류'}}});await H.ready;
  assert.equal(H.setSyntheticEnabled(true),true);
  assert.equal((await H.play('나')).status,'held');
  assert.equal((await H.optionalSynthetic('나')).status,'held');
  assert.deepEqual(sounds,[]);
});
test('missing recording may use explicitly opted-in device TTS',async()=>{
  const {H,sounds}=boot();await H.ready;
  assert.equal(H.setSyntheticEnabled(true),true);
  assert.equal((await H.optionalSynthetic('나')).status,'tts-played');
  assert.deepEqual(sounds,['나']);
});
test('manifest failure cannot override unknown held status',async()=>{
  const {H,sounds}=boot({failed:true});await H.ready;
  H.setSyntheticEnabled(true);
  assert.equal((await H.optionalSynthetic('나')).status,'manifest-error');
  assert.deepEqual(sounds,[]);
});
