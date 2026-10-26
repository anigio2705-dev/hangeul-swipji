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
  const records={},holds={};let current=null,run=0,release=null;
  const ready=fetch('./hangul-audio-manifest.json?v=20261026-human-only')
    .then(r=>{if(!r.ok)throw Error('audio manifest');return r.json()})
    .then(m=>{Object.assign(records,Object.fromEntries(Object.entries(m.recordings).filter(([,a])=>!a.disabled&&a.kind!=='synthetic')));Object.assign(holds,Object.fromEntries(Object.entries(m.recordings).filter(([,a])=>a.disabled&&a.kind!=='synthetic')));document.dispatchEvent(new Event('hs-audio-ready'))})
    .catch(()=>{document.dispatchEvent(new Event('hs-audio-ready'))});
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
    status('녹음 재생: '+word+' · Recorded voice');
    await new Promise((resolve,reject)=>{
      release=resolve;
      sound.onended=resolve;
      sound.onerror=()=>reject(Error('녹음 파일을 재생하지 못했습니다. 다시 눌러 주세요.'));
      sound.play().catch(()=>reject(Error('재생을 시작하지 못했습니다. 글자를 다시 눌러 주세요.')));
    });
    if(token===run){current=null;release=null}
  }
  async function play(value){
    stop();const token=run;
    await ready;if(token!==run)return;
    const words=Array.isArray(value)?value:[value];
    const missing=words.filter(word=>!records[word]);
    if(missing.some(w=>holds[w])){status('재생 보류: '+missing.filter(w=>holds[w]).map(w=>w+' · '+holds[w].holdReason).join(' / '));return}
    if(missing.length){status('녹음 준비 중: '+missing.join(' · ')+'. 실제 사람의 녹음이 준비될 때까지 선생님과 함께 읽어 주세요.');return}
    try{
      for(const word of words){if(token!==run)return;await recording(word,token)}
      if(token===run)status('재생 완료 · Listen and repeat.');
    }catch(e){if(token===run){stop();status(e.message)}}
  }
  const el=(tag,cls,text)=>{const x=document.createElement(tag);if(cls)x.className=cls;if(text!==undefined)x.textContent=text;return x};
  function soundButton(word,label=word){
    const b=el('button','sound notranslate',label);b.type='button';b.translate=false;
    b.dataset.sound=word;b.setAttribute('aria-label',word+' 발음 듣기');b.onclick=()=>play(word);return b;
  }
  function refreshBadges(){
    document.querySelectorAll('[data-sound]').forEach(b=>{
      const native=!!records[b.dataset.sound];b.classList.toggle('has-recording',native);
      const held=holds[b.dataset.sound];b.classList.toggle('is-held',!!held);b.title=held?held.holdReason:native?'녹음 음성 · Recorded voice':'녹음 준비 중 · Recording pending';
      b.setAttribute('aria-label',b.dataset.sound+' · '+(held?'재생 보류':native?'녹음 듣기':'녹음 준비 중'));
    });
    const n=document.querySelector('[data-recording-count]');if(n)n.textContent=Object.keys(records).length;
  }
  document.addEventListener('hs-audio-ready',refreshBadges);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)stop()});
  window.addEventListener('pagehide',stop);
  window.HSHangul={consonants,vowels,compose,records,ready,play,stop,status,el,soundButton,refreshBadges};
})();
