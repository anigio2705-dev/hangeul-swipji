'use strict';
// Disposable VM simulates an aborted, hung API request followed by a successful retry.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const html=fs.readFileSync(path.join(__dirname,'../phase3/instant-speaking.html'),'utf8');
const scripts=html.split('<script>').slice(1).map(s=>s.split('</script>')[0]);
assert.equal(scripts.length,1);
const elements=Object.create(null);
function element(id){return elements[id]||(elements[id]={hidden:false,disabled:false,textContent:'',value:'',querySelector(){return null},replaceChildren(){}});}
let requests=0,aborts=0;
const sandbox={
 document:{getElementById:element,createElement:()=>({})},
 addEventListener(){},setInterval(){return 1},clearInterval(){},
 setTimeout:fn=>setTimeout(fn,5),clearTimeout,AbortController,
 fetch:(_url,options)=>{
  requests++;
  if(requests===1)return new Promise((_resolve,reject)=>{
   options.signal.addEventListener('abort',()=>{aborts++;reject(Object.assign(Error('aborted'),{name:'AbortError'}));});
  });
  return Promise.resolve({ok:true,json:async()=>({user:{nickname:'test',role:'learner'},eligible:true,state:'idle'})});
 }
};
vm.createContext(sandbox);vm.runInContext(scripts[0],sandbox);
(async()=>{
 await new Promise(resolve=>setTimeout(resolve,30));
 assert.equal(requests,1);assert.equal(aborts,1);
 assert.match(element('error').textContent,/다시 시도/);
 await element('queue').onclick();
 assert.equal(requests,2);
 assert.equal(element('matching').hidden,false);
 assert.equal(element('error').textContent,'');
 console.log('PASS: hung instant API request aborts, serial action queue recovers and next action succeeds; no media or payment');
})().catch(e=>{console.error(e);process.exitCode=1});
