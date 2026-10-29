'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('hangul-core.js','utf8');
const board=fs.readFileSync('hangul-board.js','utf8');
const html=fs.readFileSync('hangul-basics.html','utf8');
const manifest=JSON.parse(fs.readFileSync('hangul-audio-manifest.json','utf8'));
assert.equal((source.match(/let syntheticEnabled=false/g)||[]).length,1,'one TTS state');
assert.equal((source.match(/function setSyntheticEnabled/g)||[]).length,1,'one toggle setter');
assert.equal((source.match(/function canSynthesize/g)||[]).length,1,'one capability checker');
assert.match(html,/id="allow-synthetic"/);
assert.doesNotMatch(board,/tts-opt-in/,'dead checkbox selector');
let spoken=[],started=[];
class U{constructor(text){this.text=text}}
class A{constructor(url){this.url=url} play(){started.push(this.url);queueMicrotask(()=>this.onended?.());return Promise.resolve()}pause(){}}
const doc={baseURI:'https://example.invalid/',hidden:false,querySelectorAll(){return []},querySelector(){return null},addEventListener(){},dispatchEvent(){}};
const synth={cancel(){},speak(u){spoken.push({word:u.text,lang:u.lang});queueMicrotask(()=>{u.onstart?.();u.onend?.()})}};
const win={speechSynthesis:synth,SpeechSynthesisUtterance:U,addEventListener(){}};
vm.runInNewContext(source,{window:win,document:doc,Event:class{},Audio:A,URL,fetch:async()=>({ok:true,json:async()=>manifest}),setTimeout,clearTimeout});
(async()=>{
const h=win.HSHangul;await h.ready;
const ready=Object.keys(manifest.recordings).find(k=>!manifest.recordings[k].disabled);
const held=Object.keys(manifest.recordings).find(k=>manifest.recordings[k].disabled);
assert.equal(h.consonants.length,19);assert.equal(h.vowels.length,21);
assert.equal(new Set(h.consonants.flatMap(([c])=>h.vowels.map(([v])=>h.compose(c,v)))).size,399);
assert.equal((await h.play(ready)).status,'played');assert.equal(started.length,1);
assert.equal((await h.play('힣')).status,'missing');assert.equal(spoken.length,0);
assert.equal(h.setSyntheticEnabled(true),true);
assert.equal((await h.play('힣')).status,'tts-played');
assert.equal(spoken[0].lang,'ko-KR');
assert.equal((await h.play(held)).status,'held');
assert.equal(started.length,1,'held recording never plays');
assert.equal((await h.optionalSynthetic(held)).status,'tts-played');
h.setSyntheticEnabled(false);assert.equal((await h.optionalSynthetic('힣')).status,'tts-disabled');
console.log('PASS 19+21+399, one TTS policy, mobile human priority, consent, held human blocked, explicit synthetic label');
})().catch(e=>{console.error(e);process.exitCode=1});