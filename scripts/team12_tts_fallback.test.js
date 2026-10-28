'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('hangul-core.js','utf8');
const nodes=[],events={};let speech=[],played=[];
const document={baseURI:'https://example.invalid/',hidden:false,querySelectorAll:()=>nodes,querySelector:()=>null,addEventListener:(n,f)=>{events[n]=f},dispatchEvent:e=>events[e.type]?.(e),createElement:tag=>({tagName:tag,classList:{toggle(){}},dataset:{},setAttribute(){}})};
class Audio {constructor(url){this.url=url}play(){played.push(this.url);queueMicrotask(()=>this.onplaying?.());queueMicrotask(()=>this.onended?.());return Promise.resolve()}pause(){}}
class SpeechSynthesisUtterance {constructor(text){this.text=text}}
const speechSynthesis={getVoices:()=>[{lang:'ko-KR',name:'Korean'}],cancel(){},speak(u){speech.push(u.text);queueMicrotask(()=>u.onstart?.());queueMicrotask(()=>u.onend?.())}};
const window={speechSynthesis,SpeechSynthesisUtterance,addEventListener(){}};
const manifest={recordings:{'가':{kind:'human',src:'./assets/hangul-audio/ac00.mp3',sourceUrl:'https://example.org',author:'author',license:'CC0'},'나':{kind:'human',src:'./assets/hangul-audio/b098.mp3',sourceUrl:'https://example.org',author:'author',license:'CC0',disabled:true,holdReason:'review'}}};
const context={window,document,Audio,Event:class{constructor(type){this.type=type}},fetch:async()=>({ok:true,json:async()=>manifest}),URL,Promise,queueMicrotask,setTimeout,clearTimeout};
vm.runInNewContext(source,context,{filename:'hangul-core.js'});
(async()=>{const H=window.HSHangul;await H.ready;
 assert.equal(H.compose('ㄱ','ㅏ'),'가');assert.equal(H.compose('ㅎ','ㅣ'),'히');
 assert.equal((await H.play('가')).status,'played');assert.equal(played.length,1);assert.equal(speech.length,0);
 assert.equal((await H.play('거')).status,'tts-played');assert.equal(speech.at(-1),'거');
 assert.equal((await H.play('나')).status,'tts-played');assert.equal(speech.at(-1),'나');
 H.setTtsEnabled(false);assert.equal((await H.play('거')).status,'missing');assert.equal((await H.play('나')).status,'held');
 H.setTtsEnabled(true);speechSynthesis.getVoices=()=>[];assert.equal((await H.play('거')).status,'tts-unavailable');
 assert.equal(played.length,1);console.log('PASS: human-first, missing/held TTS, explicit disabled, unavailable voice, compose');
})().catch(e=>{console.error(e);process.exitCode=1});
