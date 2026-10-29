/* Shared alphabet and audio for the board and the seven-day course. */
(() => {
  'use strict';
  const consonants = [
    ['ㄱ','기역','가'],['ㄴ','니은','나'],['ㄷ','디귿','다'],['ㄹ','리을','라'],
    ['ㅁ','미음','마'],['ㅂ','비읍','바'],['ㅅ','시옷','사'],['ㅇ','이응','아'],
    ['ㅈ','지읒','자'],['ㅊ','치읓','차'],['ㅋ','키읔','카'],['ㅌ','티읕','타'],
    ['ㅍ','피읖','파'],['ㅎ','히읗','하'],['ㄲ','쌍기역','까'],['ㄸ','쌍디귿','따'],
    ['ㅃ','쌍비읍','빠'],['ㅆ','쌍시옷','싸'],['ㅉ','쌍지읒','짜']
  ];
  const vowels = [['ㅏ','아'],['ㅑ','야'],['ㅓ','어'],['ㅕ','여'],['ㅗ','오'],
    ['ㅛ','요'],['ㅜ','우'],['ㅠ','유'],['ㅡ','으'],['ㅣ','이'],['ㅐ','애'],
    ['ㅒ','얘'],['ㅔ','에'],['ㅖ','예'],['ㅘ','와'],['ㅙ','왜'],['ㅚ','외'],
    ['ㅝ','워'],['ㅞ','웨'],['ㅟ','위'],['ㅢ','의']];
  const cOrder = [...'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'];
  const vOrder = [...'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ'];
  function compose(c,v) {
    const a=cOrder.indexOf(c),b=vOrder.indexOf(v);
    if(a<0||b<0)throw new Error('Invalid Hangul letters');
    return String.fromCharCode(0xac00+(a*21+b)*28);
  }
  const records={},holds={};let current=null,run=0,release=null,manifestError=false;
  const schedule=typeof setTimeout==='function'?setTimeout:null,cancelTimer=typeof clearTimeout==='function'?clearTimeout:()=>{};
  let manifestTimer=null;
  const request=fetch('./hangul-audio-manifest.json?v=20261027-audit').then(r=>{if(!r.ok)throw Error('audio manifest');return r.json()});
  const ready=(schedule?Promise.race([request,new Promise((_,reject)=>{manifestTimer=schedule(()=>reject(Error('audio manifest timeout')),15000)})]):request)
    .then(m=>{if(!m.recordings||typeof m.recordings!=='object')throw Error('invalid audio manifest');const human=Object.entries(m.recordings).filter(([,a])=>a.kind==='human'&&typeof a.src==='string'&&/^\.\/assets\/hangul-audio\/[\w-]+\.mp3$/.test(a.src)&&a.sourceUrl&&a.author&&a.license);Object.assign(records,Object.fromEntries(human.filter(([,a])=>!a.disabled)));Object.assign(holds,Object.fromEntries(human.filter(([,a])=>a.disabled)));document.dispatchEvent(new Event('hs-audio-ready'))})
    .catch(()=>{manifestError=true;document.dispatchEvent(new Event('hs-audio-ready'))})
    .finally(()=>{if(manifestTimer!==null)cancelTimer(manifestTimer)});
  function status(message){
    document.querySelectorAll('[data-audio-status]').forEach(x=>x.textContent=message);
  }
  function stop(){
    run++;
    if(current){current.pause();current=null}
    if(window.speechSynthesis)window.speechSynthesis.cancel();
    if(release){release();release=null}
  }
  async function recording(word,token){
    const sound=new Audio(records[word].src);current=sound;
    status('사람 녹음 재생: '+word+' · 청취 정확성 미검증 / Human recording; listening review pending');
    await new Promise((resolve,reject)=>{
      let timer=null,settled=false;
      const finish=(error)=>{if(settled)return;settled=true;if(timer!==null)cancelTimer(timer);sound.onended=null;sound.onerror=null;if(error){sound.pause();reject(error)}else resolve()};
      release=()=>finish();
      if(schedule)timer=schedule(()=>finish(Error('음성 응답 시간이 초과됐습니다. 다시 눌러 주세요. / Audio timeout; try again.')),15000);
      sound.onended=()=>finish();
      sound.onerror=()=>finish(Error('녹음 파일을 재생하지 못했습니다. 다시 눌러 주세요.'));
      try{Promise.resolve(sound.play()).catch(()=>finish(Error('재생을 시작하지 못했습니다. 글자를 다시 눌러 주세요.')))}catch(e){finish(Error('재생을 시작하지 못했습니다. 글자를 다시 눌러 주세요.'))}
    });
    if(token===run){current=null;release=null}
  }
  async function play(value){
    stop();const token=run;
    await ready;if(token!==run)return {status:'cancelled'};
    if(manifestError){status('음성 목록을 불러오지 못했습니다. 연결을 확인하고 새로고침해 주세요. / Audio list unavailable; reload to retry.');return {status:'manifest-error'}}
    const words=Array.isArray(value)?value:[value];
    if(!words.length||words.some(w=>typeof w!=='string'||!w.trim()))return {status:'invalid'};
    const missing=words.filter(word=>!records[word]);
    if(missing.some(w=>holds[w])){status('재생 보류: '+missing.filter(w=>holds[w]).map(w=>w+' · '+holds[w].holdReason).join(' / '));return {status:'held',missing}}
    if(missing.length && (words.length===1 || missing.length===words.length)){status('녹음 준비 중: '+missing.join(' · ')+'. 실제 사람의 녹음이 준비될 때까지 선생님과 함께 읽어 주세요.');return {status:'missing',missing}}
    const playable=missing.length?words.filter(word=>records[word]):words;
    try{
      for(const word of playable){if(token!==run)return {status:'cancelled'};await recording(word,token)}
      if(token===run)status(missing.length
        ?'일부만 재생했습니다. 녹음 준비 중: '+missing.join(' · ')+'. 나머지 글자는 선생님과 함께 읽어 주세요. / Partial playback; missing human recordings.'
        :'재생 완료 · 청취 정확성 미검증 / Playback ended; listening review pending.');
      if(token!==run)return {status:'cancelled'};
      return missing.length?{status:'partial',words:playable,missing}:{status:'played',words};
    }catch(e){if(token===run){stop();status(e.message)}return {status:'error',message:e.message}}
  }
  const el=(tag,cls,text)=>{const x=document.createElement(tag);if(cls)x.className=cls;if(text!==undefined)x.textContent=text;return x};
  function soundButton(word,label=word){
    const b=el('button','sound notranslate',label);b.type='button';b.translate=false;
    b.dataset.sound=word;b.setAttribute('aria-label',word+' 발음 듣기');b.onclick=()=>play(word);return b;
  }
  function refreshBadges(){
    document.querySelectorAll('[data-sound]').forEach(b=>{
      const native=!!records[b.dataset.sound];b.classList.toggle('has-recording',native);
      const held=holds[b.dataset.sound];b.classList.toggle('is-held',!!held);b.title=held?held.holdReason:native?'사람 녹음 · 청취 미검증 / Human recording; listening review pending':'녹음 준비 중 · Recording pending';
      b.setAttribute('aria-label',b.dataset.sound+' · '+(held?'재생 보류':native?'사람 녹음 듣기 · 청취 미검증':'녹음 준비 중'));
    });
    const n=document.querySelector('[data-recording-count]');if(n)n.textContent=Object.keys(records).length;
  }
  document.addEventListener('hs-audio-ready',refreshBadges);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)stop()});
  window.addEventListener('pagehide',stop);
  window.HSHangul={consonants,vowels,compose,records,ready,play,stop,status,el,soundButton,refreshBadges};
})();
