'use strict';
// Team16 product regression: all visible language pickers must follow the
// representative-approved eight, and translation must never alter Hangul glyphs.
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const root=path.join(__dirname,'..');
const read=name=>fs.readFileSync(path.join(root,name),'utf8');
const expected=['ko','en','ja','es','zh-CN','ru','mn','vi'];
const site=read('site-language.js');
const legacy=read('global-language.js');
const lab=read('global-language.html');
function codes(text,pattern){
  const match=text.match(pattern);
  assert.ok(match,'language array missing');
  return Array.from(vm.runInNewContext('('+match[1]+')'),row=>row[0]);
}
test('site selector, legacy translator and global language lab expose exactly eight approved languages',()=>{
  assert.deepEqual(codes(site,/languages=(\[[^;]+\]);/),expected);
  assert.deepEqual(codes(legacy,/const langs=(\[[^;]+\]);/),expected);
  assert.deepEqual(codes(lab,/const langs=(\[[^;]+\]);/),expected);
});
test('global language lab builds both selectors with exactly the approved options',()=>{
  const inline=lab.match(/<script>([\s\S]*?)<\/script>/);
  assert.ok(inline,'language lab inline script missing');
  new vm.Script(inline[1],{filename:'global-language.html inline script'});
  const snippet=inline[1].match(/const langs=\[[^;]+;\s*const \$=.*?from\.value="ko";to\.value="en";/s);
  assert.ok(snippet,'language lab picker initializer missing');
  const fields={from:{options:[],append(o){this.options.push(o)}},to:{options:[],append(o){this.options.push(o)}}};
  vm.runInNewContext(snippet[0],{document:{getElementById:id=>fields[id],createElement:()=>({value:'',textContent:''})}});
  for(const key of ['from','to'])assert.deepEqual(fields[key].options.map(o=>o.value),expected);
  assert.equal(fields.from.value,'ko');
  assert.equal(fields.to.value,'en');
});
test('legacy translator skips Hangul and explicitly untranslated learning controls',()=>{
  const source=legacy.match(/function nodes\(\)\{.*?return out\}/s);
  assert.ok(source,'legacy translator text walker missing');
  const make=(value,kind)=>({
    nodeValue:value,
    parentElement:{tagName:'DIV',isContentEditable:false,closest(selector){
      if(kind==='hangul'&&selector.includes('.notranslate'))return {};
      if(kind==='explicit'&&selector.includes('[translate="no"]'))return {};
      if(kind==='sound'&&selector.includes('[data-sound]'))return {};
      if(kind==='widget'&&selector.includes('#hs-global-language'))return {};
      return null;
    }}
  });
  const items=[make('가나다','hangul'),make('안녕하세요','explicit'),make('음절 발음','sound'),make('Language picker','widget'),make('Learn Korean today','normal')];
  const document={
    body:{},
    createTreeWalker(_root,_what,filter){
      const accepted=items.filter(n=>filter.acceptNode(n)===1);
      let index=-1;
      return {currentNode:null,nextNode(){this.currentNode=accepted[++index];return Boolean(this.currentNode)}};
    }
  };
  const result=vm.runInNewContext(source[0]+';nodes()', {document,excluded:new Set(['SCRIPT','STYLE','NOSCRIPT','TEXTAREA','INPUT','OPTION','CODE','PRE','SVG']),NodeFilter:{SHOW_TEXT:4,FILTER_REJECT:2,FILTER_ACCEPT:1}});
  assert.deepEqual(Array.from(result,n=>n.nodeValue),['Learn Korean today']);
});
