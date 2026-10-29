'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('hangul-core.js','utf8');
const manifest=JSON.parse(fs.readFileSync('hangul-audio-manifest.json','utf8'));
assert.equal(Object.keys(manifest.recordings).length,78);
const states=Object.values(manifest.recordings);
assert.equal(states.filter(x=>x.disabled).length,57);
let spoken=[],cancelled=0,loaded=[];
class Utterance{constructor(text){this.text=text}}
class Audio{constructor(url){loaded.push(url)}play(){queueMicrotask(()=>this.onended?.());return Promise.resolve()}pause(){}}
const doc={baseURI:'https://test.invalid/',hidden:false,querySelectorAll:()=>[],querySelector:()=>null,addEventListener(){},dispatchEvent(){}};
const synth={speak(u){spoken.push({word:u.text,lang:u.lang});queueMicrotask(()=>{u.onstart?.();u.onend?.()})},cancel(){cancelled++}};
const win={speechSynthesis:synth,SpeechSynthesisUtterance:Utterance,addEventListener(){}};
const context={window:win,document:doc,Event:class{},Audio,URL,fetch:async()=>({ok:true,json:async()=>manifest}),setTimeout,clearTimeout};
vm.runInNewContext(source,context);
(async()=>{
 const H=win.HSHangul;await H.ready;
 assert.equal(H.consonants.length,19);assert.equal(H.vowels.length,21);
 assert.equal(new Set(H.consonants.flatMap(([c])=>H.vowels.map(([v])=>H.compose(c,v)))).size,399);
 const ready=Object.keys(manifest.recordings).find(k=>!manifest.recordings[k].disabled);
 const held=Object.keys(manifest.recordings).find(k=>manifest.recordings[k].disabled);
 const missing='힣';
 assert.equal((await H.play(ready)).status,'played');assert.equal(loaded.length,1);assert.equal(spoken.length,0);
 assert.equal((await H.play(held)).status,'held');assert.equal(spoken.length,0);
 assert.equal((await H.play(missing)).status,'tts-played');assert.deepEqual(spoken.map(x=>x.word),[missing]);assert.equal(spoken[0].lang,'ko-KR');
 delete win.SpeechSynthesisUtterance;
 assert.equal((await H.play(missing)).status,'tts-unavailable');
 console.log('PASS: human recording preferred, held never played, missing Korean TTS labeled, unsupported fallback reported, 399 composition');
})().catch(e=>{console.error(e);process.exitCode=1});