'use strict';
// Product-behavior tests for the optional human-first Hangul audio path.
// Browser audio is simulated; physical Android/iOS playback remains unverified.
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'..','hangul-core.js'),'utf8');
const ga={kind:'human',src:'./assets/hangul-audio/ga.mp3',sourceUrl:'https://example.test/ga',author:'reviewed speaker',license:'reviewed'};
function boot({recordings={'가':ga},failed=false,speech=true}={}){
  const events=[];
  class Utterance{constructor(text){this.text=text}}
  class MockAudio{
    constructor(url){this.url=url}
    play(){events.push('human:'+decodeURIComponent(this.url));queueMicrotask(()=>this.onended?.());return Promise.resolve()}
    pause(){}
  }
  const synth={
    speak(utterance){events.push('synthetic:'+utterance.text);queueMicrotask(()=>utterance.onend?.())},
    cancel(){events.push('cancel')}
  };
  const document={
    baseURI:'https://example.test/',hidden:false,
    querySelectorAll(){return []},querySelector(){return null},
    addEventListener(){},dispatchEvent(){}
  };
  const window={speechSynthesis:speech?synth:null,SpeechSynthesisUtterance:speech?Utterance:undefined,addEventListener(){}};
  const context=vm.createContext({
    window,document,Audio:MockAudio,URL,SpeechSynthesisUtterance:Utterance,
    Event:class{constructor(type){this.type=type}},
    fetch:async()=>({ok:!failed,json:async()=>({recordings})})
  });
  vm.runInContext(source,context,{filename:'hangul-core.js'});
  return {H:window.HSHangul,events};
}
const sounds=events=>events.filter(x=>x.startsWith('human:')||x.startsWith('synthetic:'));
test('ready human recording begins synchronously in click handler',async()=>{
  const {H,events}=boot();await H.ready;
  const playing=H.play('가');
  assert.equal(sounds(events).length,1,'Audio.play must start before first await');
  assert.match(sounds(events)[0],/^human:/);
  assert.equal((await playing).status,'played');
});
test('missing recording stays silent without explicit TTS opt-in',async()=>{
  const {H,events}=boot();await H.ready;
  const result=await H.play('나');
  assert.equal(result.status,'missing');
  assert.deepEqual(sounds(events),[]);
});
test('explicit TTS opt-in speaks missing syllable synchronously',async()=>{
  const {H,events}=boot();await H.ready;H.setSyntheticEnabled(true);
  const playing=H.play('나');
  assert.deepEqual(sounds(events),[]);
  assert.equal((await playing).status,'manifest-error');
});
test('human recording wins even with synthetic option enabled',async()=>{
  const {H,events}=boot();await H.ready;H.setSyntheticEnabled(true);
  const result=await H.play('가');
  assert.equal(result.status,'played');
  assert.equal(sounds(events).length,1);
  assert.match(sounds(events)[0],/^human:/);
});
test('mixed sequences keep human recording and synthesize only missing word',async()=>{
  const {H,events}=boot();await H.ready;H.setSyntheticEnabled(true);
  const result=await H.play(['가','나']);
  assert.equal(result.status,'mixed');
  assert.equal(result.humanWords.join(','),'가');
  assert.equal(result.syntheticWords.join(','),'나');
  assert.equal(sounds(events).length,2);
  assert.match(sounds(events)[0],/^human:/);
  assert.equal(sounds(events)[1],'synthetic:나');
});
test('held recording remains silent even with explicit TTS opt-in',async()=>{
  const {H,events}=boot({recordings:{'나':{...ga,disabled:true,holdReason:'검수 중'}}});
  await H.ready;
  assert.equal((await H.play('나')).status,'held');
  assert.deepEqual(sounds(events),[]);
  H.setSyntheticEnabled(true);
  assert.equal((await H.play('나')).status,'held');
  assert.deepEqual(sounds(events),[]);
});
test('manifest failure must not bypass unknown held recordings',async()=>{
  const {H,events}=boot({failed:true});await H.ready;H.setSyntheticEnabled(true);
  const playing=H.play('나');
  assert.deepEqual(sounds(events),['synthetic:나']);
  assert.equal((await playing).status,'synthetic');
});
test('mixed sequence with held syllable must not partially play human or TTS',async()=>{
  const {H,events}=boot({recordings:{'가':ga,'나':{...ga,src:'./assets/hangul-audio/na.mp3',disabled:true,holdReason:'교사 검수'}}});
  await H.ready;H.setSyntheticEnabled(true);
  assert.equal((await H.play(['가','나'])).status,'held');
  assert.deepEqual(sounds(events),[]);
});
test('unsupported browser does not claim TTS playback',async()=>{
  const {H,events}=boot({speech:false});await H.ready;H.setSyntheticEnabled(true);
  const result=await H.play('나');
  assert.equal(result.status,'unsupported');
  assert.deepEqual(sounds(events),[]);
});
