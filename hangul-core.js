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
  const records=Object.create(null),holds=Object.create(null);let current=null,run=0,release=null,manifestError=false,manifestLoaded=false;
  const schedule=typeof setTimeout==='function'?setTimeout:null,cancelTimer=typeof clearTimeout==='function'?clearTimeout:()=>{};
  let loading=null;
  function loadManifest(){
    if(loading)return loading;
    let timer=null;
    const request=fetch('./hangul-audio-manifest.json?v=20261027-audio-retry', {cache:'no-store'})
      .then(r=>{if(!r.ok)throw Error('audio manifest');return r.json()});
    loading=(schedule?Promise.race([request,new Promise((_,reject)=>{timer=schedule(()=>reject(Error('audio manifest timeout')),15000)})]):request)
      .then(m=>{if(!m.recordings||typeof m.recordings!=='object'||Array.isArray(m.recordings))throw Error('invalid audio manifest');const seenSources=new Set(),seenDigests=new Set();
        const human=Object.entries(m.recordings).filter(([word,a])=>{
          // Reject reserved object property names and blank keys from untrusted manifests.
          if(!word.trim()||['__proto__','constructor','prototype'].includes(word))return false;
          if(!a||a.kind!=='human'||typeof a.src!=='string'||!/^\.\/assets\/hangul-audio\/[\w-]+\.mp3$/.test(a.src)||
             !/^[a-f0-9]{64}$/i.test(a.sha256||'')||typeof a.sourceUrl!=='string'||!/^https:\/\/[^\s]+$/.test(a.sourceUrl)||
             typeof a.author!=='string'||!a.author.trim()||typeof a.license!=='string'||!a.license.trim())return false;
          // Never allow one recording file to impersonate multiple distinct letters.
          if(seenSources.has(a.src)||seenDigests.has(a.sha256.toLowerCase()))return false;
          seenSources.add(a.src);seenDigests.add(a.sha256.toLowerCase());return true;
        });
        // Replace stale inventory on refresh; removed/held files must not remain playable.
        for(const key of Object.keys(records))delete records[key];
        for(const key of Object.keys(holds))delete holds[key];
        Object.assign(records,Object.fromEntries(human.filter(([,a])=>!a.disabled)));
        Object.assign(holds,Object.fromEntries(human.filter(([,a])=>a.disabled)));
        manifestError=false;manifestLoaded=true;document.dispatchEvent(new Event('hs-audio-ready'))})
      .catch(()=>{manifestError=true;manifestLoaded=false;document.dispatchEvent(new Event('hs-audio-ready'))})
      .finally(()=>{if(timer!==null)cancelTimer(timer);loading=null});
    return loading;
  }
  const ready=loadManifest();
  async function reloadManifest(){
    stop();
    status('사람 녹음 목록을 다시 확인하고 있습니다. / Checking recordings…');
    // A manual refresh must fetch fresh data even if the initial request is still
    // pending. Reusing that initial promise would leave a just-uploaded file unseen.
    if(loading)await loading;
    await loadManifest();
    if(manifestError){
      status('음원 목록 연결에 실패했습니다. 다시 확인을 눌러 주세요. / Recording list unavailable; retry.');
      return {status:'manifest-error'};
    }
    refreshBadges();
    const count=Object.keys(records).length;
    status('음원 목록 확인 완료 · 재생 가능 '+count+'개 · 검수 대기 '+Object.keys(holds).length+'개. 없는 녹음은 재생하지 않습니다.');
    return {status:'ready',count};
  }
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
    const asset=new URL(records[word].src, document.baseURI);
    // Version the URL by the reviewed file digest: a replacement at the same path
    // must not replay a stale browser/CDN-cached recording after manifest refresh.
    const digest=records[word].sha256;
    if(typeof digest==='string'&&/^[0-9a-f]{64}$/i.test(digest))asset.searchParams.set('v',digest.slice(0,16));
    const sound=new Audio(asset.href);sound.preload='auto';current=sound;
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
  // Educational fallback: device TTS is explicitly opt-in and never human audio.
  let syntheticEnabled=false;
  function canSynthesize(){return !!(window.speechSynthesis&&typeof window.SpeechSynthesisUtterance==='function')}
  function setSyntheticEnabled(value){
    syntheticEnabled=!!value&&canSynthesize();
    if(!syntheticEnabled)stop();
    status(syntheticEnabled?'기기 합성음 보조 사용 · 사람 녹음이 아닙니다.':'기기 합성음 보조 꺼짐.');
    return syntheticEnabled;
  }
  async function synthesized(word,token){
    if(!canSynthesize())return {status:'tts-unavailable',word};
    return new Promise(resolve=>{
      const speech=new SpeechSynthesisUtterance(word);
      speech.lang='ko-KR';speech.rate=.85;
      let finished=false,timer=null;
      const finish=result=>{if(finished)return;finished=true;if(timer!==null)cancelTimer(timer);if(release===cancel)release=null;resolve(result)};
      const cancel=()=>finish({status:'cancelled',word});
      release=cancel;
      speech.onstart=()=>{if(token===run)status('기기 합성음 재생 중 · 사람 녹음 아님: '+word)};
      speech.onend=()=>finish({status:token===run?'tts-played':'cancelled',word});
      speech.onerror=()=>finish({status:'tts-error',word});
      if(schedule)timer=schedule(()=>{window.speechSynthesis.cancel();finish({status:'tts-timeout',word})},15000);
      try{window.speechSynthesis.speak(speech)}catch(_){finish({status:'tts-error',word})}
    });
  }
  async function play(value){
    stop();const token=run;
    // Do not await an already loaded manifest: even a resolved await yields the
    // user click activation on some mobile browsers, causing Audio.play() to
    // reject with NotAllowedError despite a valid human recording.
    if(!manifestLoaded)await (manifestError?loadManifest():(loading||ready));
    if(token!==run)return {status:'cancelled'};
    if(manifestError){status('음성 목록을 불러오지 못했습니다. 글자를 다시 누르면 재시도합니다. / Audio list unavailable; click again to retry.');return {status:'manifest-error'}}
    const words=Array.isArray(value)?value:[value];
    if(!words.length||words.some(w=>typeof w!=='string'||!w.trim()))return {status:'invalid'};
    const missing=words.filter(word=>!records[word]);
    if(missing.some(w=>holds[w])){status('재생 보류: '+missing.filter(w=>holds[w]).map(w=>w+' · '+holds[w].holdReason).join(' / '));return {status:'held',missing}}
    if(missing.length&&!syntheticEnabled){status('녹음 준비 중: '+missing.join(' · ')+'. 사람 녹음이 없으며, 원하면 기기 합성음 보조를 켜세요.');return {status:'missing',missing}}
    try{
      let ttsUsed=false;
      for(const word of words){if(token!==run)return {status:'cancelled'};if(records[word]){await recording(word,token)}else {ttsUsed=true;const output=await synthesized(word,token);if(output.status!=='tts-played'){if(token===run)status('기기 합성음 재생 불가: '+word+' · '+output.status);return output}}}
      if(token===run)status(ttsUsed?'기기 합성음 포함 재생 종료 · 사람 녹음 아님':'사람 녹음 재생 완료 · 청취 정확성 미검증');
      return {status:token===run?(ttsUsed?'tts-played':'played'):'cancelled',words};
    }catch(e){if(token===run){stop();status(e.message)}return {status:'error',message:e.message}}
  }
  // The shared opt-in flag and helpers are declared once above. A second
  // declaration made this entire file a SyntaxError on the team12 branch.
  function synthesize(word,token){
    return new Promise(resolve=>{
      if(!canSynthesize())return resolve({status:'tts-unsupported'});
      if(token!==run)return resolve({status:'cancelled'});
      const utterance=new window.SpeechSynthesisUtterance(word);
      utterance.lang='ko-KR';utterance.rate=.82;
      let finished=false,timer=null;
      const done=(result)=>{if(finished)return;finished=true;if(timer!==null)cancelTimer(timer);release=null;resolve(result)};
      release=()=>done({status:'cancelled'});
      if(schedule)timer=schedule(()=>{window.speechSynthesis.cancel();done({status:'tts-timeout'})},12000);
      utterance.onstart=()=>{if(token===run)status('기기 한국어 합성음 재생 중: '+word+' · 사람 녹음 아님')};
      utterance.onend=()=>done({status:'tts-played'});
      utterance.onerror=()=>done({status:'tts-error'});
      try{window.speechSynthesis.speak(utterance)}catch(_){done({status:'tts-error'})}
    });
  }
  // For absent/held recordings, the explicit opt-in fallback runs after a user
  // gesture; a held human file itself is never played. Human files remain first.
  async function optionalSynthetic(word){
    stop();const token=run;
    if(!syntheticEnabled)return {status:'tts-disabled'};
    // Do not synthesize if the manifest is unavailable: the recording could
    // be deliberately held for teacher review. A failed fetch is not consent.
    if(!manifestLoaded||manifestError){
      status('음성 목록 확인 전에는 합성음을 재생할 수 없습니다. / Audio manifest unavailable.');
      return {status:'manifest-error'};
    }
    if(holds[word]){
      status('검수 보류 음성은 합성음으로도 우회하지 않습니다: '+word);
      return {status:'held',word};
    }
    if(records[word])return {status:'human-available',word};
    return synthesize(word,token);
  }
  const el=(tag,cls,text)=>{const x=document.createElement(tag);if(cls)x.className=cls;if(text!==undefined)x.textContent=text;return x};
  function soundButton(word,label=word){
    const b=el('button','sound notranslate',label);b.type='button';b.translate=false;
    b.dataset.sound=word;b.setAttribute('aria-label',word+' 발음 듣기');b.onclick=()=>play(word);return b;
  }
  function refreshBadges(){
    document.querySelectorAll('[data-sound]').forEach(b=>{
      const info=availability(b.dataset.sound);b.dataset.audioState=info.state;
      const native=info.state==='ready';b.classList.toggle('has-recording',native);b.classList.toggle('audio-unavailable',!native);b.setAttribute('aria-description',info.label);
      const held=info.state==='held'?holds[b.dataset.sound]:null;b.classList.toggle('is-held',!!held);b.setAttribute('aria-label',b.dataset.sound+' · '+info.label);
      b.title=info.label;
    });
    const n=document.querySelector('[data-recording-count]');if(n)n.textContent=manifestError?'확인 불가':Object.keys(records).length;
    const summary=document.querySelector('[data-board-audio-counts]');
    if(summary){
      const cells=[...document.querySelectorAll('.board [data-sound]')];
      const counts={ready:0,held:0,missing:0,unavailable:0};
      for(const cell of cells)counts[availability(cell.dataset.sound).state]++;
      summary.textContent='글자판 '+cells.length+'칸 · 재생 가능 '+counts.ready+' · 검수 보류 '+counts.held+' · 녹음 없음 '+counts.missing+(counts.unavailable?' · 목록 오류 '+counts.unavailable:'')+' (청취 승인 전)';
    }
  }
  document.addEventListener('hs-audio-ready',refreshBadges);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)stop()});
  window.addEventListener('pagehide',stop);
  window.HSHangul={consonants,vowels,compose,records,ready,reloadManifest,availability,play,stop,status,el,soundButton,refreshBadges,canSynthesize,setSyntheticEnabled,optionalSynthetic};
})();
