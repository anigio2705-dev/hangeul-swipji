/* Human-only recording capture queue; no TTS, upload, or approval shortcuts. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(root)root.HSRecordingQueue=api;
})(typeof window==='object'?window:null,function(){
  'use strict';
  const consonants=[...'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'];
  const vowels=[...'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ'];
  const priority=[...'고 노 누 도 라 마 바 자 카 타 파 하'.split(' ')];
  function build(manifest){
    if(!manifest||!manifest.recordings||typeof manifest.recordings!=='object'||Array.isArray(manifest.recordings))
      throw new TypeError('Invalid recording manifest');
    const entries=[];
    for(let i=0;i<consonants.length;i++)for(let j=0;j<vowels.length;j++){
      const character=String.fromCharCode(0xac00+(i*21+j)*28);
      const record=Object.prototype.hasOwnProperty.call(manifest.recordings,character)?manifest.recordings[character]:null;
      const status=!record?'missing':record.disabled?'held':'ready_unapproved';
      entries.push({character,status,filename:'hangul-human-'+character.codePointAt(0).toString(16)+'.webm'});
    }
    const order=new Map(priority.map((c,i)=>[c,i]));
    entries.sort((a,b)=>(order.get(a.character)??999)-(order.get(b.character)??999));
    const counts={missing:0,held:0,ready_unapproved:0};
    for(const item of entries)counts[item.status]++;
    return {entries,counts,missing:entries.filter(x=>x.status==='missing')};
  }
  return Object.freeze({build});
});
