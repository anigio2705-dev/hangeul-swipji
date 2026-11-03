/* Non-destructive sync of seven course completion maps to the authenticated test server. */
(function(root){
'use strict';
const keys=['hs-intro-v1','hs-beginner1-v1','hs-beginner2-v1','hs-intermediate1-v1','hs-intermediate2-v1','hs-advanced1-v1','hs-advanced2-v1'];
const ownerKey='hs-team12-progress-owner';
function completed(raw){try{const x=JSON.parse(raw||'{}');return x&&typeof x.done==='object'&&x.done?Object.keys(x.done).filter(k=>/^(?:[0-9]|[1-4][0-9])$/.test(k)&&x.done[k]===true).map(Number):[]}catch(_){return []}}
function merge(raw,lessons){let x;try{x=JSON.parse(raw||'{}')}catch(_){x={}}if(!x||typeof x!=='object'||Array.isArray(x))x={};if(!x.done||typeof x.done!=='object'||Array.isArray(x.done))x.done={};for(const lesson of lessons)if(Number.isInteger(lesson)&&lesson>=1&&lesson<=50)x.done[lesson-1]=true;return JSON.stringify(x)}
function client(fetcher,storage,notify){
 const pending=new Set();let authenticated=false,activeUid=null,generation=0,flushing=false,activePost=null;
 async function request(path,options){const response=await fetcher(path,Object.assign({credentials:'same-origin',cache:'no-store'},options||{}));if(!response.ok)throw Error('HTTP '+response.status);return response.json()}
 function archiveOnSwitch(uid){
  const previousOwner=storage.getItem(ownerKey);
  if(previousOwner===uid)return;
  for(const key of keys){const previous=storage.getItem(key);if(previous!==null){const archiveKey=previousOwner?'hs-team12-account-'+previousOwner+'-'+key:'hs-team12-unowned-'+key;storage.setItem(archiveKey,previous);storage.removeItem(key)}}
  pending.clear();storage.setItem(ownerKey,uid);
 }
 async function pull(){
  const mine=++generation;authenticated=false;
  if(activePost&&typeof activePost.abort==='function')activePost.abort();
  try{
   const identity=await request('/api/me');const uid=identity?.user?.id;
   if(!uid)throw Error('missing account identity');
   // Verify the server response before claiming ownership or touching stored progress.
   const data=await request('/api/free-progress');
   if(!Array.isArray(data.completed))throw Error('invalid progress response');
   if(mine!==generation)return false;
   const owner=String(uid);
   archiveOnSwitch(owner);
   activeUid=owner;authenticated=true;
   const groups=Array.from({length:7},()=>[]);
   for(const row of data.completed){if(Number.isInteger(row.stage)&&row.stage>=1&&row.stage<=7&&Number.isInteger(row.lesson)&&row.lesson>=1&&row.lesson<=50)groups[row.stage-1].push(row.lesson)}
   for(let i=0;i<7;i++){const old=storage.getItem(keys[i]);const updated=(old===null&&groups[i].length===0)?null:merge(old,groups[i]);if(updated!==null&&updated!==old){storage.setItem(keys[i],updated);notify?.()}}
   enqueueAll();await flush();return mine===generation;
  }catch(_){if(mine===generation){authenticated=false;activeUid=null}return false}
 }
 function changed(key,raw){const stage=keys.indexOf(key)+1;if(!stage)return;if(!authenticated||!activeUid||storage.getItem(ownerKey)!==activeUid)return;for(const lesson of completed(raw))pending.add(stage+':'+(lesson+1));void flush()}
 async function flush(){
  if(flushing||!authenticated||!activeUid)return;
  flushing=true;
  const mine=generation,uid=activeUid;
  try{
   while(pending.size&&authenticated&&mine===generation&&activeUid===uid&&storage.getItem(ownerKey)===uid){
    const id=pending.values().next().value;const [stage,lesson]=id.split(':').map(Number);
    const controller=typeof AbortController==='function'?new AbortController():null;
    activePost=controller;
    try{
     // Never start a POST unless the local owner still matches the authenticated pull.
     if(mine!==generation||storage.getItem(ownerKey)!==uid)break;
     await request('/api/free-progress',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({stage,lesson}),...(controller?{signal:controller.signal}:{})});
     if(mine!==generation||activeUid!==uid)break;
     pending.delete(id);
    }catch(_){if(mine===generation){authenticated=false;activeUid=null}break}
    finally{if(activePost===controller)activePost=null}
   }
  }finally{flushing=false;if(pending.size&&authenticated&&activeUid&&generation!==mine)void flush()}
 }
 function enqueueAll(){for(const key of keys)changed(key,storage.getItem(key))}
 return {pull,changed,enqueueAll,flush,pending};
}
root.HSTeam12ServerProgress={keys,completed,merge,client};
})(typeof window==='object'?window:globalThis);
