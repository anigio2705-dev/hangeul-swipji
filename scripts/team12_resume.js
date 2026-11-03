/* Pure progress selection shared by dashboard and non-operational tests. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(root)root.HSTeam12Resume=api;
})(typeof window==='object'?window:null,function(){
  'use strict';
  function nextLesson(record,total=50){
    if(!Number.isInteger(total)||total<1||total>350)throw new RangeError('invalid lesson count');
    const done=record&&typeof record==='object'&&record.done&&typeof record.done==='object'&&!Array.isArray(record.done)?record.done:{};
    for(let i=0;i<total;i++)if(done[i]!==true)return i+1;
    return total;
  }
  function lessonFromQuery(search,total=50){
    const raw=new URLSearchParams(search).get('unit');
    if(raw===null||!/^[0-9]+$/.test(raw))return null;
    const n=Number(raw);
    return Number.isSafeInteger(n)&&n>=1&&n<=total?n:null;
  }
  return Object.freeze({nextLesson,lessonFromQuery});
});
