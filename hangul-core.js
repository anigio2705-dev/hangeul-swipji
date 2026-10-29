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
  const records={},holds={};let current=null,run=0,release=null,manifestError=false,manifestLoaded=false;
  const schedule=typeof setTimeout==='function'?setTimeout:null,cancelTimer=typeof clearTimeout==='function'?clearTimeout:()=>{};
  let loading=null;
  function loadManifest(){
    if(loading)return loading;
    let timer=null;
    const request=fetch('./hangul-audio-manifest.json?v=20261027-audio-retry', {cache:'no-store'})
      .then(r=>{if(!r.ok)throw Error('audio manifest');return r.json()});
    loading=(schedule?Promise.race([request,new Promise((_,reject)=>{timer=schedule(()=>reject(Error('audio manifest timeout')),15000)})]):request)
      .then(m=>{if(!m.recordings||typeof m.recordings!=='object')throw Error('invalid audio manifest');const human=Object.entries(m.recordings).filter(([,a])=>a.kind==='human'&&typeof a.src==='string'&&/^\.\/assets\/hangul-audio\/[\w-]+\.mp3$/.test(a.src)&&a.sourceUrl&&a.author&&a.license);Object.assign(records,Object.fromEntries(human.filter(([,a])=>!a.disabled)));Object.assign(holds,Object.fromEntries(human.filter(([,a])=>a.disabled)));manifestError=false;manifestLoaded=true;document.dispatchEvent(new Event('hs-audio-ready'))})
      .catch(()=>{manifestError=true;manifestLoaded=false;document.dispatchEvent(new Event('hs-audio-ready'))})
      .finally(()=>{if(timer!==null)cancelTimer(timer);loading=null});
    return loading;
  }
  const ready=loadManifest();
  function availability(word){
    if(manifestError)return {state:'unavailable',label:'목록 연결 오류 · 다시 눌러 재시도'};
    if(records[word])return {state:'ready',label:'♪ 사람 녹음 듣기 · 청취 검수 전'};
    if(holds[word])return {state:'held',label:'검수 대기 · '+holds[word].holdReason};
    return {state:'missing',label:'녹음 없음 · 실제 사람 녹음 필요'};
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
  // Optional device TTS is not a human recording and never silently replaces one.
  let syntheticEnabled=false;
  function canSynthesize(){return !!(window.speechSynthesis&&typeof window.SpeechSynthesisUtterance==='function')}
  function setSyntheticEnabled(value){
    syntheticEnabled=!!value;
    if(!syntheticEnabled)stop();
    status(syntheticEnabled?'기기 합성음(TTS) 보조가 켜졌습니다. 사람 녹음이 아닙니다.':'기기 합성음(TTS) 보조가 꺼졌습니다.');
    return syntheticEnabled;
  }
  function tts(word,token){
    return new Promise(resolve=>{
      if(!canSynthesize())return resolve({status:'unsupported',message:'이 브라우저는 기기 합성음을 지원하지 않습니다.'});
      const utterance=new SpeechSynthesisUtterance(word);
      utterance.lang='ko-KR';utterance.rate=.82;utterance.pitch=1;
      let done=false,timer=null;
      const finish=(result)=>{
        if(done)return;done=true;
        if(timer!==null)cancelTimer(timer);
        release=null;resolve(result);
      };
      release=()=>finish({status:'cancelled'});
      if(schedule)timer=schedule(()=>{
        window.speechSynthesis.cancel();
        finish({status:'error',message:'합성음이 응답하지 않습니다. 기기 한국어 음성을 확인해 주세요.'});
      },12000);
      utterance.onstart=()=>{if(token===run)status('기기 합성음 재생 중: '+word+' · 사람 녹음이 아닙니다. / Device synthetic voice')};
      utterance.onend=()=>finish({status:'synthetic',word});
      utterance.onerror=()=>finish({status:'error',message:'기기 합성음을 재생하지 못했습니다. 한국어 음성 설정을 확인해 주세요.'});
      try{window.speechSynthesis.speak(utterance)}catch(_){finish({status:'error',message:'기기 합성음을 시작하지 못했습니다.'})}
    });
  }
  async function fallback(words,token){
    if(!syntheticEnabled)return null;
    for(const word of words){
      if(token!==run)return {status:'cancelled'};
      const result=await tts(word,token);
      if(result.status!=='synthetic'){if(token===run)status(result.message||'합성음 재생 취소');return result}
    }
    if(token===run)status('기기 합성음 재생 종료 · 사람 녹음이 아닙니다. 발음 정확성은 기기에 따라 다릅니다.');
    return {status:token===run?'synthetic':'cancelled',words};
  }
  async function play(value){
    stop();const token=run;
    const words=Array.isArray(value)?value:[value];
    if(!words.length||words.some(w=>typeof w!=='string'||!w.trim()))return {status:'invalid'};
    // A device TTS click must not wait for a failing manifest request: some
    // mobile browsers lose user activation after an await, even if it resolves.
    // Fail closed: without the manifest we cannot know whether a recording
    // is deliberately held for teacher review, even with explicit TTS opt-in.
    if(manifestError){
      status('음성 목록을 확인할 수 없습니다. 합성음으로 검수 보류를 우회하지 않습니다.');
      return {status:'manifest-error'};
    }
    // Same for available human recordings: start Audio.play synchronously in
    // the user gesture when the manifest has already been loaded.
    if(!manifestLoaded)await (manifestError?loadManifest():(loading||ready));
    if(token!==run)return {status:'cancelled'};
    if(manifestError){
      status('음성 목록을 불러오지 못했습니다. 글자를 다시 누르면 재시도합니다. / Audio list unavailable; click again to retry.');
      return {status:'manifest-error'};
    }
    const missing=words.filter(word=>!records[word]);
    // A held recording is a review prohibition, not merely a missing file.
    // Reject the whole sequence before any human or synthetic audio starts.
    const held=missing.filter(word=>holds[word]);
    if(held.length){
      status('재생 보류: '+held.map(w=>w+' · '+holds[w].holdReason).join(' / '));
      return {status:'held',missing};
    }
    // Without explicit opt-in, never play a partial sequence or silently
    // replace an unavailable human recording with a synthetic voice.
    if(missing.length&&!syntheticEnabled){
      const held=missing.filter(w=>holds[w]);
      if(held.length){
        status('재생 보류: '+held.map(w=>w+' · '+holds[w].holdReason).join(' / '));
        return {status:'held',missing};
      }
      status('녹음 준비 중: '+missing.join(' · ')+'. 실제 사람의 녹음이 준비될 때까지 선생님과 함께 읽어 주세요.');
      return {status:'missing',missing};
    }
    const humanWords=[],syntheticWords=[];
    try{
      // Preserve the caller's order. A valid human recording ALWAYS wins,
      // including when a later syllable in the same sequence is unavailable.
      for(const word of words){
        if(token!==run)return {status:'cancelled'};
        if(records[word]){
          await recording(word,token);
          humanWords.push(word);
        }else{
          const result=await fallback([word],token);
          if(!result||result.status!=='synthetic')return result||{status:'missing',missing:[word]};
          syntheticWords.push(word);
        }
      }
      if(token===run){
        status(syntheticWords.length
          ?'재생 완료 · 사람 녹음 '+humanWords.length+'개, 기기 합성음 '+syntheticWords.length+'개 (사람 녹음 아님).'
          :'재생 완료 · 사람 녹음 청취 정확성 미검증 / Playback ended; listening review pending.');
      }
      return {status:token!==run?'cancelled':syntheticWords.length?(humanWords.length?'mixed':'synthetic'):'played',words,humanWords,syntheticWords};
    }catch(e){
      if(token===run){stop();status(e.message)}
      return {status:'error',message:e.message};
    }
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
      const held=holds[b.dataset.sound];b.classList.toggle('is-held',!!held);b.title=held?held.holdReason:native?'사람 녹음 · 청취 미검증 / Human recording; listening review pending':'녹음 준비 중 · Recording pending';
      b.setAttribute('aria-label',b.dataset.sound+' · '+info.label);
      b.title=info.label;
    });
    const n=document.querySelector('[data-recording-count]');if(n)n.textContent=Object.keys(records).length;
  }
  document.addEventListener('hs-audio-ready',refreshBadges);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)stop()});
  window.addEventListener('pagehide',stop);
  window.HSHangul={consonants,vowels,compose,records,ready,availability,play,stop,status,el,soundButton,refreshBadges,setSyntheticEnabled,canSynthesize};
})();
