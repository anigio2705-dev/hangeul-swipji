'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, 'hq_preserved_page_enhancements.js'), 'utf8');
function element(tag = 'div') {
  const handlers = {};
  return {tag, style:{}, parentNode:null, children:[], value:'ko', classList:{removed:[],remove(x){this.removed.push(x)}},
    addEventListener(k,fn){handlers[k]=fn}, trigger(k){handlers[k]?.()}, setAttribute(k,v){this[k]=v},
    appendChild(x){this.children.push(x);x.parentNode=this;return x},
    insertBefore(x,y){this.children.splice(this.children.indexOf(y),0,x);x.parentNode=this},
    scrollIntoView(){this.scrolled=true}};
}
function environment(path) {
  const nodes = {}, handlers = {}, doc = {readyState:'complete', hidden:false, head:element(), body:element(),
    getElementById:k=>nodes[k]||null, querySelector:k=>nodes[k]||null,
    createElement:element, addEventListener(k,fn){handlers[k]=fn}, trigger(k){handlers[k]?.()}};
  const root = {document:doc, location:{pathname:path,reloaded:0,reload(){this.reloaded++}},
    setTimeout(fn){fn()}, requestAnimationFrame(fn){fn()}, addEventListener(k,fn){handlers['window:'+k]=fn},
    fetch:async()=>({ok:false}), localStorage:{getItem(){return null}}};
  return {root,doc,nodes,handlers};
}
function run(e) {vm.runInNewContext(source,{window:e.root,globalThis:e.root,Promise});}
(async()=>{
  const r=environment('/reading.html');
  const head=element(),progress=element(),side=element(),lang=element('select');
  lang.value='ko';r.nodes.progress=progress;r.nodes['.layout>.side']=side;
  r.nodes['.library .sectionhead']=head;r.nodes.lang=lang;
  head.appendChild(progress);
  r.doc.getElementById=k=>k==='changeLevel'?head.children[0]?.children[0]||null:r.nodes[k]||null;
  run(r);
  const button=head.children[0].children[0];
  assert.equal(button.id,'changeLevel');assert.equal(button.textContent,'레벨 변경');
  assert.equal(head.children[0].children[1],progress);
  button.trigger('click');assert.deepEqual(r.doc.body.classList.removed,['reading-level-open']);assert.equal(side.scrolled,true);
  lang.value='en';lang.trigger('change');assert.equal(button.textContent,'Change level');
  assert.equal(button['aria-controls'],'levels');
  const c=environment('/beginner1.html');let changed=[];let pulled=0;
  let current='{"done":{}}';c.root.localStorage={getItem(){return current}};
  c.root.HSTeam12ServerProgress={client(){return {changed(k,v){changed.push([k,v])},pull(){pulled++;return Promise.resolve(true)}}}};
  run(c);
  assert.equal(c.doc.head.children.length,1);
  assert.equal(c.doc.head.children[0].src,'./scripts/team12_server_progress.js');
  c.doc.head.children[0].onload();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(pulled,1);assert.equal(c.root.location.reloaded,0);
  current='{"done":{"0":true}}';c.doc.trigger('click');
  assert.deepEqual(changed,[['hs-beginner1-v1',current]]);
  c.doc.trigger('click');assert.equal(changed.length,1,'unchanged progress must not resend');
  const restored=environment('/advanced2.html');let restore='{}';restored.root.localStorage={getItem(){return restore}};
  restored.root.HSTeam12ServerProgress={client(){return {changed(){},pull(){restore='{"done":{"2":true}}';return Promise.resolve(true)}}}};
  run(restored);restored.doc.head.children[0].onload();await new Promise(resolve=>setImmediate(resolve));
  assert.equal(restored.root.location.reloaded,1,'authenticated restore refreshes original course UI');
  const other=environment('/index.html');run(other);assert.equal(other.doc.head.children.length,0);
  console.log('Preserved HTML additive reading switch and course sync: 12 assertions PASS');
})().catch(e=>{console.error(e);process.exitCode=1});
