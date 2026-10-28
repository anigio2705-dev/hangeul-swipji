'use strict';
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../hangul-core.js'),'utf8');
const meta={kind:'human',src:'./assets/hangul-audio/test.mp3',sourceUrl:'https://example.org/source',author:'Recorded speaker',license:'CC BY-SA 4.0',sha256:'a'.repeat(64)};
function setup(mode='ended',fetchMode='ok'){
 let played=0,synthetic=0,fetches=0;const statuses=[],urls=[],counts={},badgeClasses={},badgeLabels={};
 const badge={dataset:{sound:'가'},classList:{toggle(name,value){badgeClasses[name]=value}},setAttribute(name,value){badgeLabels[name]=value}};
 const c={URL,setTimeout:(f,t)=>setTimeout(f,Math.min(t,10)),clearTimeout,Event:function(){},window:{addEventListener(){},speechSynthesis:{cancel(){},speak(){synthetic++}}},document:{baseURI:'https://example.org/',addEventListener(){},dispatchEvent(){},querySelectorAll(selector){return selector==='[data-sound]'?[badge]:[{set textContent(v){statuses.push(v)}}]},querySelector(selector){return selector==='[data-recording-count]'?{set textContent(v){counts.recording=v}}:null}},fetch:()=>{fetches++;if(fetchMode==='retry'&&fetches===1)return Promise.reject(Error('temporary'));if(fetchMode==='refresh-fail'&&fetches>1)return Promise.reject(Error('refresh failed'));return fetchMode==='hang'?new Promise(()=>{}):fetchMode==='reject'?Promise.reject(Error('network')):Promise.resolve({ok:true,json:async()=>fetchMode==='json-hang'?new Promise(()=>{}):({recordings:fetchMode==='version'?{가:{...meta,sha256:(fetches===1?'a':'b').repeat(64)}}:fetchMode==='rotate'&&fetches>1?{나:meta,아:{...meta,src:'./assets/hangul-audio/test-held.mp3',sha256:'c'.repeat(64),disabled:true,holdReason:'listening pending'}}:fetchMode==='bad-hash'?{가:{...meta,sha256:'invalid'}}:fetchMode==='insecure-source'?{가:{...meta,sourceUrl:'http://example.org/source'}}:fetchMode==='no-author'?{가:{...meta,author:''}}:fetchMode==='duplicate-source'?{가:meta,나:{...meta}}:fetchMode==='duplicate-hash'?{가:meta,나:{...meta,src:'./assets/hangul-audio/copied.mp3'}}:fetchMode==='prototype-key'?{['__proto__']:{...meta},constructor:{...meta,src:'./assets/hangul-audio/constructor.mp3'},가:{...meta,src:'./assets/hangul-audio/valid.mp3'}}:{가:meta,아:{...meta,src:'./assets/hangul-audio/test-held.mp3',sha256:'c'.repeat(64),disabled:true,holdReason:'listening pending'},machine:{...meta,kind:'synthetic'},unknown:{...meta,kind:'unknown'},external:{...meta,src:'https://example.org/a.mp3'}}})})},Audio:class{constructor(src){played++;urls.push(src)}pause(){}play(){if(mode==='throw')throw Error('blocked');if(mode==='reject')return Promise.reject(Error('blocked'));if(mode==='hang')return Promise.resolve();return Promise.resolve().then(()=>mode==='error'?this.onerror?.():this.onended?.())}}};
 vm.createContext(c);vm.runInContext(source,c);return {h:c.window.HSHangul,stats:()=>({played,synthetic,statuses,urls,counts,badgeClasses,badgeLabels})};
}
(async()=>{
 const a=setup();await a.h.ready;
 for(const word of ['missing','machine','unknown','external'])assert.equal((await a.h.play(word)).status,'missing');
 assert.equal((await a.h.play('아')).status,'held');assert.equal(a.stats().played,0);
 assert.equal((await a.h.play('가')).status,'played');assert.equal(a.stats().played,1);assert.equal(a.stats().synthetic,0);
 for(const mode of ['throw','reject','error','hang']){const x=setup(mode);await x.h.ready;assert.equal((await x.h.play('가')).status,'error',mode)}
 for(const fetchMode of ['reject','hang','json-hang']){const x=setup('ended',fetchMode);assert.equal((await x.h.play('가')).status,'manifest-error',fetchMode)}
 const failedCount=setup('ended','reject');await failedCount.h.ready;
 failedCount.h.refreshBadges();
 assert.equal(failedCount.stats().counts.recording,'확인 불가','failed manifest must not advertise stale playable recordings');
 for(const mode of ['bad-hash','insecure-source','no-author']){
  const invalid=setup('ended',mode);await invalid.h.ready;
  assert.equal(invalid.h.availability('가').state,'missing',mode);
  assert.equal((await invalid.h.play('가')).status,'missing',mode);
  assert.equal(invalid.stats().played,0,mode);
 }
 const duplicate=setup('ended','duplicate-source');await duplicate.h.ready;
 assert.equal(duplicate.h.availability('가').state,'ready');
 assert.equal(duplicate.h.availability('나').state,'missing','same file cannot masquerade as two letters');
 const copied=setup('ended','duplicate-hash');await copied.h.ready;
 assert.equal(copied.h.availability('가').state,'ready');
 assert.equal(copied.h.availability('나').state,'missing','same audio bytes cannot be relabeled as a different syllable');
 const polluted=setup('ended','prototype-key');await polluted.h.ready;
 for(const word of ['__proto__','constructor','toString']){
  assert.equal(polluted.h.availability(word).state,'missing',word+' must not resolve through Object.prototype');
  assert.equal((await polluted.h.play(word)).status,'missing');
 }
 assert.equal(polluted.h.availability('가').state,'ready');
 const stale=setup('ended','refresh-fail');await stale.h.ready;
 stale.h.refreshBadges();assert.equal(stale.stats().badgeClasses['has-recording'],true);
 assert.equal((await stale.h.reloadManifest()).status,'manifest-error');
 stale.h.refreshBadges();assert.equal(stale.stats().badgeClasses['has-recording'],false,'manifest failure must clear stale ready badge');
 assert.match(stale.stats().badgeLabels['aria-label'],/목록 연결 오류/);
 const retry=setup('ended','retry');await retry.h.ready;assert.equal(retry.h.availability('가').state,'unavailable');assert.equal((await retry.h.play('가')).status,'played');assert.equal(retry.h.availability('가').state,'ready');assert.equal(retry.h.availability('아').state,'held');assert.equal(retry.h.availability('missing').state,'missing');
 const early=setup('ended','rotate');
 // User may press refresh while the first manifest request is still pending.
 assert.equal((await early.h.reloadManifest()).status,'ready');
 assert.equal(early.h.availability('가').state,'missing','manual refresh must not reuse stale initial response');
 assert.equal(early.h.availability('나').state,'ready');
 const rotating=setup('ended','rotate');await rotating.h.ready;
 assert.equal(rotating.h.availability('가').state,'ready');
 assert.equal((await rotating.h.reloadManifest()).status,'ready');
 assert.equal(rotating.h.availability('가').state,'missing','removed recording must not remain playable');
 assert.equal(rotating.h.availability('나').state,'ready');
 assert.equal((await rotating.h.play('가')).status,'missing');
 assert.equal((await rotating.h.play('나')).status,'played');
 const versioned=setup('ended','version');await versioned.h.ready;
 assert.equal((await versioned.h.play('가')).status,'played');
 assert.equal((await versioned.h.reloadManifest()).status,'ready');
 assert.equal((await versioned.h.play('가')).status,'played');
 const urls=versioned.stats().urls;
 assert.equal(urls.length,2);assert(urls[0].includes('v=aaaaaaaaaaaaaaaa'));
 assert(urls[1].includes('v=bbbbbbbbbbbbbbbb'));
 assert.notEqual(urls[0],urls[1],'replaced audio at same path must have a new URL');
 const x=setup('hang');await x.h.ready;const pending=x.h.play('가');await Promise.resolve();await Promise.resolve();x.h.stop();assert.equal((await pending).status,'cancelled');
 console.log('PASS audio runtime: ended, held, missing, source-type rejection, play rejection, file error, manifest failure, timeout, cancellation and atomic manifest refresh (including initial-load overlap), versioned audio cache invalidation, failure-safe recording count and badges, strict hash/source validation, duplicate file/digest rejection and prototype-key safety; no TTS substitution.');
})().catch(e=>{console.error(e);process.exitCode=1});
