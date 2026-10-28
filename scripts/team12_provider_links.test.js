'use strict';
/* Execute the actual learner handoff code with virtual browser controls. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const script=fs.readFileSync(require('node:path').join(__dirname,'team12_provider_links.js'),'utf8');
function scenario(role){
 const store=new Map();const listeners={};
 const link={dataset:{team12Provider:role},addEventListener(name,fn){listeners[name]=fn}};
 const sandbox={document:{querySelectorAll(q){assert.equal(q,'a[data-team12-provider]');return [link]}},sessionStorage:{setItem(k,v){store.set(k,v)}}};
 vm.runInNewContext(script,sandbox,{timeout:1000});
 assert.equal(typeof listeners.click,'function');listeners.click();
 return store.get('hs-team12-provider-intent');
}
assert.equal(scenario('teacher'),'teacher');
assert.equal(scenario('partner'),'partner');
assert.equal(scenario('administrator'),undefined);
assert.equal(scenario(''),undefined);
console.log('team12 virtual browser provider intent tests passed');
