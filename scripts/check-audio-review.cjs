'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..');
const script=fs.readFileSync(path.join(root,'hangul-audio-review.js'),'utf8');
const inventory=JSON.parse(fs.readFileSync(path.join(root,'hangul-audio-manifest.json'),'utf8'));
const audit=JSON.parse(fs.readFileSync(path.join(root,'hangul-audio-audit.json'),'utf8'));
assert.equal(audit.recordings.length,Object.keys(inventory.recordings).length);
for(const item of audit.recordings){
 const recording=inventory.recordings[item.text];
 assert(recording&&recording.kind==='human'&&recording.src===item.src&&/^[a-f0-9]{64}$/i.test(recording.sha256),'audit and playback inventory must match: '+item.text);
}
new vm.Script(script,{filename:'hangul-audio-review.js'});
const report={scope:'test',counts:{excludedSynthetic:0,targets:1,humanFiles:1,playbackAvailable:1,held:0},week:{available:1,targets:1,missing:0},
 recordings:[{text:'가',src:'./assets/hangul-audio/a.mp3',kind:'human',groups:['7일 과정'],sourceUrl:'https://example.org/a',duration:1,leadingSilence:0,trailingSilence:0,signalWarnings:[]}],targets:[{text:'가',groups:['7일 과정'],recordingAvailable:true}]};
const saved=new Map();
async function mount(hash,override){
 const elements=new Map(),created=[];
 class Element{
  constructor(tag){this.tag=tag;this.children=[];this.value='';this.textContent='';this.disabled=false;created.push(this);}
  append(...children){this.children.push(...children)}
  replaceChildren(...children){this.children=children}
  setAttribute(){}
  pause(){}
 }
 const byId=id=>{if(!elements.has(id))elements.set(id,new Element('div'));return elements.get(id)};
 byId('filter').value='recorded';
 const doc={getElementById:byId,createElement:tag=>new Element(tag),querySelectorAll:selector=>selector==='audio'?created.filter(e=>e.tag==='audio'):[]};
 const current={recordings:{가:{kind:'human',src:override||'./assets/hangul-audio/a.mp3',sha256:hash}}};
 const localStorage={getItem:key=>saved.get(key)||null,setItem:(key,value)=>saved.set(key,value)};
 const context={document:doc,location:{search:'',href:'https://example.org/hangul-audio-review.html'},localStorage,URL,URLSearchParams,Blob,setTimeout,
 fetch:async url=>({ok:true,json:async()=>url.includes('audit')?report:current})};
 vm.createContext(context);vm.runInContext(script,context);
 await new Promise(resolve=>setImmediate(resolve));
 return {created,byId};
}
(async()=>{
 const first=await mount('a'.repeat(64));
 const audio=first.created.find(x=>x.tag==='audio');
 assert(audio.src.includes('v=aaaaaaaaaaaaaaaa'),'playback must be cache-busted by recording hash');
 audio.onended();
 const select=first.created.find(x=>x.tag==='select');
 select.value='checked';select.onchange();
 assert(saved.get('hs-audio-review-v1').includes('a'.repeat(64)),'notes must be tied to digest');
 const replaced=await mount('b'.repeat(64));
 assert.equal(replaced.created.find(x=>x.tag==='select').value,'pending','replacement audio must not inherit prior listening notes');
 assert(replaced.created.find(x=>x.tag==='audio').src.includes('v=bbbbbbbbbbbbbbbb'));
 const mismatch=await mount('c'.repeat(64),'./assets/hangul-audio/other.mp3');
 assert.equal(mismatch.byId('export').disabled,true,'mismatched audit must disable export');
 assert.equal(mismatch.created.filter(x=>x.tag==='audio').length,0,'mismatched audit must not offer playback');
 console.log('PASS: audit/manifest integrity, digest-bound review notes, cache-safe playback, mismatch fail-closed.');
})().catch(error=>{console.error(error);process.exitCode=1});
