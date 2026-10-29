'use strict';
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../hangul-core.js'),'utf8');
const meta={kind:'human',src:'./assets/hangul-audio/test.mp3',sourceUrl:'https://example.org/source',author:'Recorded speaker',license:'CC BY-SA 4.0'};
function setup(mode='ended',fetchMode='ok'){
 let played=0,synthetic=0,fetches=0;const statuses=[];
 const c={setTimeout:(f,t)=>setTimeout(f,Math.min(t,10)),clearTimeout,Event:function(){},window:{addEventListener(){},speechSynthesis:{cancel(){},speak(){synthetic++}}},document:{addEventListener(){},dispatchEvent(){},querySelectorAll(){return[{set textContent(v){statuses.push(v)}}]}},fetch:()=>{fetches++;if(fetchMode==='retry'&&fetches===1)return Promise.reject(Error('temporary'));return fetchMode==='hang'?new Promise(()=>{}):fetchMode==='reject'?Promise.reject(Error('network')):Promise.resolve({ok:true,json:async()=>fetchMode==='json-hang'?new Promise(()=>{}):({recordings:{가:meta,아:{...meta,disabled:true,holdReason:'listening pending'},machine:{...meta,kind:'synthetic'},unknown:{...meta,kind:'unknown'},external:{...meta,src:'https://example.org/a.mp3'}}})})},Audio:class{constructor(){played++}pause(){}play(){if(mode==='throw')throw Error('blocked');if(mode==='reject')return Promise.reject(Error('blocked'));if(mode==='hang')return Promise.resolve();return Promise.resolve().then(()=>mode==='error'?this.onerror?.():this.onended?.())}}};
 vm.createContext(c);vm.runInContext(source,c);return {h:c.window.HSHangul,stats:()=>({played,synthetic,statuses})};
}
(async()=>{
 const a=setup();await a.h.ready;
 for(const word of ['missing','machine','unknown','external'])assert.equal((await a.h.play(word)).status,'missing');
 assert.equal((await a.h.play('아')).status,'held');assert.equal(a.stats().played,0);
 assert.equal((await a.h.play('가')).status,'played');assert.equal(a.stats().played,1);assert.equal(a.stats().synthetic,0);
 for(const mode of ['throw','reject','error','hang']){const x=setup(mode);await x.h.ready;assert.equal((await x.h.play('가')).status,'error',mode)}
 for(const fetchMode of ['reject','hang','json-hang']){const x=setup('ended',fetchMode);assert.equal((await x.h.play('가')).status,'manifest-error',fetchMode)}
 const retry=setup('ended','retry');await retry.h.ready;assert.equal(retry.h.availability('가').state,'unavailable');await retry.h.retryManifest();assert.equal(retry.h.availability('가').state,'ready');assert.equal((await retry.h.play('가')).status,'played');assert.equal(retry.h.availability('가').state,'ready');assert.equal(retry.h.availability('아').state,'held');assert.equal(retry.h.availability('missing').state,'missing');
 const x=setup('hang');await x.h.ready;const pending=x.h.play('가');await Promise.resolve();await Promise.resolve();x.h.stop();assert.equal((await pending).status,'cancelled');
 console.log('PASS audio runtime: ended, held, missing, source-type rejection, play rejection, file error, manifest failure, timeout and cancellation; no TTS substitution.');
})().catch(e=>{console.error(e);process.exitCode=1});
