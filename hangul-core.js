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
  // TTS is explicitly labelled as synthesized speech, never as a human recording.
  let ttsEnabled=true;
  const schedule=typeof setTimeout==='function'?setTimeout:null,cancelTimer=typeof clearTimeout==='function'?clearTimeout:()=>{};
  let loading=null;
  function loadManifest(){
    if(loading)return loading;
    let timer=null;
    const request=fetch('./hangul-audio-manifest.json?v=20261027-audio-retry', {cache:'no-store'})
      .then(r=>{if(!r.ok)throw Error('audio manifest');return r.json()});
    loading=(schedule?Promise.race([request,new Promise((_,reject)=>{timer=schedule(()=>reject(Error('audio manifest timeout')),15000)})]):request)
      .then(m=>{if(!m.recordings||typeof m.recordings!=='object')throw Error('invalid audio manifest');const human=Object.entries(m.recordings).filter(([,a])=>a.kind==='human'&&typeof a.src==='string'&&/^\.\/assets\/hangul-audio\/[\w-]+\.mp3$/.test(a.src)&&a.sourceUrl&&a.author&&a.license);Object.assign(records,Object.fromEntries(human.filter(([,a])=>!a.disabled)));Object.assign(holds,Object.fromEntries(human.filter(([,a])=>a.disabled)));manifestError=false;document.dispatchEvent(new Event('hs-audio-ready'))})
      .catch(()=>{manifestError=true;document.dispatchEvent(new Event('hs-audio-ready'))})
      .finally(()=>{if(timer!==null)cancelTimer(timer);loading=null});
    return loading;
  }
  const ready=loadManifest();
  function availability(word){
    if(manifestError)return {state:ttsEnabled?'tts':'unavailable',label:ttsEnabled?'합성 음성(TTS) · 음원 목록 연결 오류':'목록 연결 오류 · 다시 눌러 재시도'};
    if(records[word])return {state:'ready',label:'♪ 사람 녹음 듣기 · 청취 검수 전'};
    if(holds[word])return {state:ttsEnabled?'tts-held':'held',label:'사람 녹음 검수 대기 · '+(ttsEnabled?'합성 음성(TTS) 사용':'재생 불가')};
    return {state:ttsEnabled?'tts':'missing',label:ttsEnabled?'합성 음성(TTS) · 사람 녹음 없음':'녹음 없음 · 실제 사람 녹음 필요'};
  }
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
    const sound=new Audio(new URL(records[word].src, document.baseURI).href);current=sound;
    status('사람 녹음 로딩 중: '+word+' · 청취 정확성 미검증 / Loading human recording; listening review pending');
    await new Promise((resolve,reject)=>{
      let timer=null,settled=false;
      const finish=(error)=>{if(settled)return;settled=true;if(timer!==null)cancelTimer(timer);sound.onended=null;sound.onerror=null;sound.onplaying=null;if(error){sound.pause();reject(error)}else resolve()};
      release=()=>finish();
      if(schedule)timer=schedule(()=>finish(Error('음성 응답 시간이 초과됐습니다. 다시 눌러 주세요. / Audio timeout; try again.')),15000);
      sound.onplaying=()=>{if(token===run)status('사람 녹음 재생 중: '+word+' · 청취 정확성 미검증 / Playing human recording; listening review pending')};
      sound.onended=()=>finish();
      sound.onerror=()=>finish(Error('녹음 파일을 재생하지 못했습니다. 다시 눌러 주세요.'));
      try{Promise.resolve(sound.play()).catch(()=>finish(Error('재생을 시작하지 못했습니다. 글자를 다시 눌러 주세요.')))}catch(e){finish(Error('재생을 시작하지 못했습니다. 글자를 다시 눌러 주세요.'))}
    });
    if(token===run){current=null;release=null}
  }
  async function synthesize(word,token){
    const synth=window.speechSynthesis;
    if(!ttsEnabled||!synth||typeof window.SpeechSynthesisUtterance!=='function'){
      const message='이 기기에서는 한국어 합성 음성(TTS)을 사용할 수 없습니다. / Korean TTS unavailable.';
      status(message);return {status:'tts-unavailable',message};
    }
    const voices=typeof synth.getVoices==='function'?synth.getVoices():[];
    const korean=voices.find(v=>/^ko(?:-|$)/i.test(v.lang||''));
    if(!korean){const message='한국어 음성(ko-KR)이 설치되지 않았습니다. 기기의 한국어 음성을 설치해 주세요. / No Korean voice installed.';status(message);return {status:'tts-unavailable',message}}
    return new Promise(resolve=>{
      let finished=false,timer=null;
      const finish=(result)=>{if(finished)return;finished=true;if(timer!==null)cancelTimer(timer);if(release===cancel)release=null;resolve(result)};
      const cancel=()=>finish({status:'cancelled'});
      release=cancel;
      const u=new window.SpeechSynthesisUtterance(word);
      u.lang='ko-KR';u.voice=korean;u.rate=0.85;
      u.onstart=()=>{if(token===run)status('합성 음성(TTS) 재생 중: '+word+' · 실제 사람 녹음이 아닙니다. / Synthesized Korean speech')};
      u.onend=()=>finish({status:token===run?'tts-played':'cancelled',words:[word]});
      u.onerror=()=>finish({status:'tts-error',message:'한국어 TTS 재생 오류 · 기기 음성 설정을 확인하세요.'});
      if(schedule)timer=schedule(()=>{synth.cancel();finish({status:'tts-error',message:'TTS 응답 시간 초과'})},15000);
      try{synth.speak(u)}catch(e){finish({status:'tts-error',message:'한국어 TTS 시작 실패'})}
    });
  }
  async function play(value){
    stop();const token=run;
    await (manifestError?loadManifest():(loading||ready));if(token!==run)return {status:'cancelled'};
    if(manifestError&&!ttsEnabled){status('음성 목록을 불러오지 못했습니다. 글자를 다시 누르면 재시도합니다. / Audio list unavailable; click again to retry.');return {status:'manifest-error'}}
    const words=Array.isArray(value)?value:[value];
    if(!words.length||words.some(w=>typeof w!=='string'||!w.trim()))return {status:'invalid'};
    const missing=words.filter(word=>!records[word]);
    if(missing.length&&!ttsEnabled){const held=missing.some(w=>holds[w]);status(held?'사람 녹음 검수 보류':'사람 녹음 준비 중');return {status:held?'held':'missing',missing}}
    try{
      for(const word of words){if(token!==run)return {status:'cancelled'};if(records[word]&&!manifestError){await recording(word,token)}else{const result=await synthesize(word,token);if(result.status!=='tts-played')return result}}
      if(token===run)status('발음 재생 완료 · 사람 녹음은 청취 검수 전, TTS는 합성 음성입니다.');
      return {status:token===run?(missing.length?'tts-played':'played'):'cancelled',words};
    }catch(e){if(token===run){stop();status(e.message)}return {status:'error',message:e.message}}
  }
  const el=(tag,cls,text)=>{const x=document.createElement(tag);if(cls)x.className=cls;if(text!==undefined)x.textContent=text;return x};
  function soundButton(word,label=word){
    const b=el('button','sound notranslate',label);b.type='button';b.translate=false;
    b.dataset.sound=word;b.setAttribute('aria-label',word+' 발음 듣기');b.onclick=()=>play(word);return b;
  }
  function refreshBadges(){
    document.querySelectorAll('[data-sound]').forEach(b=>{
      const info=availability(b.dataset.sound);b.dataset.audioState=info.state;
      const native=!!records[b.dataset.sound];b.classList.toggle('has-recording',native);
      const held=holds[b.dataset.sound];b.classList.toggle('is-held',!!held);b.title=held?held.holdReason:native?'사람 녹음 · 청취 미검증 / Human recording; listening review pending':'합성 음성(TTS) 또는 음원 없음';
      b.setAttribute('aria-label',b.dataset.sound+' · '+info.label);
      b.title=info.label;
    });
    const n=document.querySelector('[data-recording-count]');if(n)n.textContent=Object.keys(records).length;
  }
  document.addEventListener('hs-audio-ready',refreshBadges);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)stop()});
  window.addEventListener('pagehide',stop);
  function setTtsEnabled(enabled){ttsEnabled=!!enabled;refreshBadges();return ttsEnabled}
  window.HSHangul={consonants,vowels,compose,records,ready,availability,play,stop,status,el,soundButton,refreshBadges,setTtsEnabled};
})();
