'use strict';
// Independent browser-DOM simulation of #43, using the real core and board scripts.
// This is NOT a real-browser, audio-listening or public-site approval.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..');
class E{
 constructor(tag='div'){this.tagName=tag;this.children=[];this.dataset={};this.attributes={};this.textContent='';this.classList={toggle(){}};}
 append(...nodes){this.children.push(...nodes);}
 appendChild(node){this.children.push(node);return node;}
 replaceChildren(...nodes){this.children=nodes;}
 setAttribute(k,v){this.attributes[k]=v;}
}
const ids=new Map(),get=id=>{if(!ids.has(id))ids.set(id,new E());return ids.get(id)};
const walk=(node,fn)=>node.children.flatMap(n=>[...(fn(n)?[n]:[]),...walk(n,fn)]);
const handlers=new Map();
const document={
 baseURI:'https://example.invalid/hangul-basics.html',hidden:false,
 getElementById:get,createElement:tag=>new E(tag),
 addEventListener:(name,fn)=>handlers.set(name,fn),
 dispatchEvent:e=>handlers.get(e.type)?.(e),
 querySelectorAll:s=>s==='.board [data-sound]'?['basic-board','extended-board'].flatMap(id=>walk(get(id),n=>!!n.dataset.sound)):s==='[data-sound]'?[...ids.values()].flatMap(n=>walk(n,x=>!!x.dataset.sound)):[],
 querySelector:()=>null,
};
const window={addEventListener(){},speechSynthesis:{cancel(){},speak(){throw Error('TTS forbidden')}}};
const sandbox=vm.createContext({window,document,console,URL,Event:class{constructor(type){this.type=type}},
 fetch:async()=>({ok:true,json:async()=>({recordings:{}})}),
 setTimeout,clearTimeout,Audio:class{constructor(){throw Error('No recording supplied')}}});
for(const file of ['hangul-core.js','hangul-board.js'])
 vm.runInContext(fs.readFileSync(path.join(root,file),'utf8'),sandbox,{filename:file,timeout:1000});
(async()=>{
 await window.HSHangul.ready;
 const H=window.HSHangul;
 const consonants=[...'ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎㄲㄸㅃㅆㅉ'];
 const vowels=[...'ㅏㅑㅓㅕㅗㅛㅜㅠㅡㅣㅐㅒㅔㅖㅘㅙㅚㅝㅞㅟㅢ'];
 assert.deepEqual(Array.from(H.consonants,x=>x[0]),consonants);
 assert.deepEqual(Array.from(H.vowels,x=>x[0]),vowels);
 assert.equal(get('consonants').children.length,19);
 assert.equal(get('vowels').children.length,21);
 const basic=walk(get('basic-board'),n=>!!n.dataset.sound);
 const extended=walk(get('extended-board'),n=>!!n.dataset.sound);
 assert.equal(basic.length,190);assert.equal(extended.length,209);
 const all=[...basic,...extended],sounds=new Set(all.map(x=>x.dataset.sound));
 assert.equal(sounds.size,399);
 for(const c of consonants)for(const v of vowels)assert.ok(sounds.has(H.compose(c,v)),c+'+'+v);
 const click=word=>{const node=all.find(n=>n.dataset.sound===word);assert.ok(node);node.onclick()};
 click('가');assert.equal(get('selected-syllable').textContent,'가');
 assert.equal(get('selected-formula').textContent,'ㄱ + ㅏ = 가');
 click('괘');assert.equal(get('selected-syllable').textContent,'괘');
 assert.equal(get('selected-formula').textContent,'ㄱ + ㅙ = 괘');
 get('repeat-selected').onclick();
 assert.equal(get('builder-c').children.length,19);
 assert.equal(get('builder-v').children.length,21);
 console.log('PASS #43: 19 consonants, 21 vowels, 399 unique clickable cells, basic/extended selection, repeat, builder');
})().catch(e=>{console.error(e);process.exitCode=1});
