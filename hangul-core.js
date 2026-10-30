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
  let loading=null, pendingRefreshes=0;
  function loadManifest(){
    if(loading)return loading;
    // A refresh must revoke the old inventory immediately. Otherwise taps during
    // the network request can play a recording that has just been withdrawn.
    manifestLoaded=false;
    manifestError=false;
    let timer=null;
    const request=fetch('./hangul-audio-manifest.json?v=20261027-audio-retry', {cache:'no-store'})
      .then(r=>{if(!r.ok)throw Error('audio manifest');return r.json()});
    loading=(schedule?Promise.race([request,new Promise((_,reject)=>{timer=schedule(()=>reject(Error('audio manifest timeout')),15000)})]):request)
      .then(m=>{if(!m.recordings||typeof m.recordings!=='object'||Array.isArray(m.recordings))throw Error('invalid audio manifest');const seenSources=new Set(),seenDigests=new Set();
        // Review holds are a safety decision, not a playable-audio assertion.
        // A withdrawn file may have no src/hash, or duplicate a quarantined
        // source. Preserve the hold BEFORE validating playable recordings.
        // Otherwise an opted-in device TTS could speak a review-held syllable.
        const blocked=Object.entries(m.recordings).filter(([word,a])=>
          !!word.trim()&&!['__proto__','constructor','prototype'].includes(word)&&
          a&&typeof a==='object'&&!!a.disabled
        ).map(([word,a])=>[word,{holdReason:typeof a.holdReason==='string'&&a.holdReason.trim()
          ?a.holdReason:'검수 보류 · 음원 정보 확인 필요'}]);
        const human=Object.entries(m.recordings).filter(([word,a])=>{
          // Reject reserved object property names and blank keys from untrusted manifests.
          if(!word.trim()||['__proto__','constructor','prototype'].includes(word))return false;
          if(!a||a.disabled||a.kind!=='human'||typeof a.src!=='string'||!/^\.\/assets\/hangul-audio\/[\w-]+\.mp3$/.test(a.src)||
             !/^[a-f0-9]{64}$/i.test(a.sha256||'')||typeof a.sourceUrl!=='string'||!/^https:\/\/[^\s]+$/.test(a.sourceUrl)||
             typeof a.author!=='string'||!a.author.trim()||typeof a.license!=='string'||!a.license.trim())return false;
          // Never allow one recording file to impersonate multiple distinct letters.
          if(seenSources.has(a.src)||seenDigests.has(a.sha256.toLowerCase()))return false;
          seenSources.add(a.src);seenDigests.add(a.sha256.toLowerCase());return true;
        });
        // Replace stale inventory on refresh; removed/held files must not remain playable.
        for(const key of Object.keys(records))delete records[key];
        for(const key of Object.keys(holds))delete holds[key];
        Object.assign(records,Object.fromEntries(human));
        Object.assign(holds,Object.fromEntries(blocked));
        manifestError=false;manifestLoaded=true;document.dispatchEvent(new Event('hs-audio-ready'))})
      .catch(()=>{manifestError=true;manifestLoaded=false;document.dispatchEvent(new Event('hs-audio-ready'))})
      .finally(()=>{if(timer!==null)cancelTimer(timer);loading=null});
    return loading;
  }
  const ready=loadManifest();
  async function reloadManifest(){
    stop();
    // An older in-flight manifest can complete while a refresh is queued.
    // Keep playback blocked until EVERY queued refresh has finished, including
    // the microtask gap between the old response and the new network request.
    pendingRefreshes++;
    status('사람 녹음 목록을 다시 확인하고 있습니다. / Checking recordings…');
    try{
      // A manual refresh must fetch fresh data even if the initial request is
      // pending. Reusing that initial promise could retain a withdrawn file.
      if(loading)await loading;
      const refresh=loadManifest();
      refreshBadges();
      await refresh;
      if(manifestError){
        status('음원 목록 연결에 실패했습니다. 다시 확인을 눌러 주세요. / Recording list unavailable; retry.');
        return {status:'manifest-error'};
      }
      const count=Object.keys(records).length;
      status('음원 목록 확인 완료 · 재생 가능 '+count+'개 · 검수 대기 '+Object.keys(holds).length+'개. 없는 녹음은 재생하지 않습니다.');
      return {status:'ready',count};
    }finally{
      pendingRefreshes--;
      refreshBadges();
    }
  }
  function availability(word){
    if(pendingRefreshes)return {state:'unavailable',label:'음원 목록 재확인 중 · 준비되면 다시 눌러 주세요'};
    if(manifestError)return {state:'unavailable',label:'목록 연결 오류 · 다시 눌러 재시도'};
    if(!manifestLoaded)return {state:'unavailable',label:'음원 목록 확인 중 · 준비되면 다시 눌러 주세요'};
    if(records[word])return {state:'ready',label:'♪ 사람 녹음 듣기 · 청취 검수 전'};
    if(holds[word])return {state:'held',label:'검수 대기 · '+holds[word].holdReason};
    return {state:'missing',label:'녹음 없음 · 실제 사람 녹음 필요'};
  }
  function status(message){
    document.querySelectorAll('[data-audio-status]').forEach(x=>x.textContent=message);
  }
  function stop(){
    run++;
    // Resolve the active playback as cancelled BEFORE invoking browser stop
    // methods. Safari/Chrome may synchronously emit onend during
    // speechSynthesis.cancel(); if it fires first, direct optionalSynthetic()
    // falsely reports tts-played even though the user left the page.
    const cancelActive=release;
    release=null;
    if(cancelActive)cancelActive();
    if(current){current.pause();current=null}
    if(window.speechSynthesis)window.speechSynthesis.cancel();
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
  async function play(value){
    stop();const token=run;
    // Stale click callbacks may run after pagehide, even if document.hidden
    // has not yet changed. Only a foreground tap may start new playback.
    if(document.hidden===true||wasHidden){
      status('화면 복귀 후 글자를 다시 눌러 주세요. / Return to this page and tap again.');
      return {status:'cancelled'};
    }
    // Do not await an already loaded manifest: even a resolved await yields the
    // user click activation on some mobile browsers, causing Audio.play() to
    // reject with NotAllowedError despite a valid human recording.
    if(pendingRefreshes){status('음원 목록 재확인 중입니다. 준비되면 다시 눌러 주세요.');return {status:'loading'}}
    if(!manifestLoaded){
      // Mobile browsers require Audio.play() during the original tap. Waiting for
      // a network manifest loses transient user activation, so ask for a fresh tap.
      if(manifestError){void loadManifest();status('음원 목록을 다시 연결하고 있습니다. 준비되면 글자를 다시 눌러 주세요.');return {status:'manifest-error'}}
      status('음원 목록을 불러오는 중입니다. 준비되면 글자를 다시 눌러 주세요.');
      return {status:'loading'};
    }
    if(token!==run)return {status:'cancelled'};
    if(manifestError){status('음성 목록을 불러오지 못했습니다. 글자를 다시 누르면 재시도합니다. / Audio list unavailable; click again to retry.');return {status:'manifest-error'}}
    const words=Array.isArray(value)?value:[value];
    if(!words.length||words.some(w=>typeof w!=='string'||!w.trim()))return {status:'invalid'};
    const missing=words.filter(word=>!records[word]);
    // A review hold is a hard block, including when device TTS is opted in.
    // Only genuinely absent (not held) recordings may use optional synthetic speech.
    const held=missing.filter(w=>holds[w]);
    if(held.length){status('재생 보류: '+held.map(w=>w+' · '+holds[w].holdReason).join(' / '));return {status:'held',missing}}
    if(!syntheticEnabled&&missing.length&&(words.length===1||missing.length===words.length)){
      status('녹음 준비 중: '+missing.join(' · ')+'. 실제 사람의 녹음이 준비될 때까지 선생님과 함께 읽어 주세요.');
      return {status:'missing',missing};
    }
    // Only skip genuinely absent recordings; review-held recordings remain a
    // hard block for the entire sequence. Never silently synthesize without opt-in.
    const playable=!syntheticEnabled&&missing.length?words.filter(w=>records[w]):words;
    try{
      let usedSynthetic=false;
      for(const word of playable){
        if(token!==run)return {status:'cancelled'};
        if(records[word]){await recording(word,token);continue}
        const result=await synthesize(word,token);
        if(result.status!=='tts-played'){
          if(token===run)status('기기 한국어 합성음 재생 불가: '+word+' · '+result.status+' / Synthetic voice unavailable');
          return {status:result.status,word,missing};
        }
        usedSynthetic=true;
      }
      if(token===run)status(usedSynthetic?'재생 완료 · 기기 합성음 사용 · 사람 녹음 아님':missing.length&&!syntheticEnabled
        ?'일부만 재생했습니다. 녹음 준비 중: '+missing.join(' · ')+'. 나머지 글자는 선생님과 함께 읽어 주세요. / Partial human playback; recordings missing.'
        :'사람 녹음 재생 완료 · 청취 정확성 미검증');
      if(token!==run)return {status:'cancelled'};
      return missing.length&&!syntheticEnabled?{status:'partial',words:playable,missing}:{status:usedSynthetic?'tts-played':'played',words};
    }catch(e){if(token===run){stop();status(e.message)}return {status:'error',message:e.message}}
  }
  // Optional Korean device TTS: never impersonates a human recording.
  // Keep OFF by default and refuse playback of recordings explicitly on hold.
  let syntheticEnabled=false;
  function canSynthesize(){return !!(window.speechSynthesis&&typeof window.SpeechSynthesisUtterance==='function')}
  function setSyntheticEnabled(value){
    syntheticEnabled=!!value;
    stop(); // revoke any current playback immediately when consent changes
    status(syntheticEnabled?'기기 합성음 보조 켜짐 · 사람 녹음 아님':'기기 합성음 보조 꺼짐');
    refreshBadges();
    return syntheticEnabled;
  }
  function synthesize(word,token){
    return new Promise(resolve=>{
      if(!canSynthesize())return resolve({status:'tts-unsupported'});
      if(token!==run)return resolve({status:'cancelled'});
      const utterance=new window.SpeechSynthesisUtterance(word);
      utterance.lang='ko-KR';utterance.rate=.82;
      let finished=false,timer=null;
      const done=(result)=>{if(finished)return;finished=true;if(timer!==null)cancelTimer(timer);if(release===cancelSynthetic)release=null;resolve(result)};
      const cancelSynthetic=()=>done({status:'cancelled'});
      release=cancelSynthetic;
      // The browser may synchronously emit onend inside cancel(). Settle timeout first.
      if(schedule)timer=schedule(()=>{done({status:'tts-timeout'});try{window.speechSynthesis.cancel()}catch(_){}},12000);
      utterance.onstart=()=>{if(token===run)status('기기 한국어 합성음 재생 중: '+word+' · 사람 녹음 아님')};
      utterance.onend=()=>done({status:'tts-played'});
      utterance.onerror=()=>done({status:'tts-error'});
      try{window.speechSynthesis.speak(utterance)}catch(_){done({status:'tts-error'})}
    });
  }
  // Only absent, non-held recordings may use opt-in device synthesis.
  // Do not bypass a withdrawn/held human recording via this direct API.
  async function optionalSynthetic(word){
    stop();const token=run;
    if(document.hidden===true||wasHidden)return {status:'cancelled'};
    if(!syntheticEnabled)return {status:'tts-disabled'};
    // This public API must reject malformed input just like play(); otherwise
    // browsers can speak an empty string or coerce null/arrays into speech.
    if(typeof word!=='string'||!word.trim())return {status:'invalid'};
    // Direct TTS must obey the same refresh lock as human recordings: a
    // withdrawn/held letter may appear only in the newer pending manifest.
    if(pendingRefreshes)return {status:'loading'};
    if(!manifestLoaded||manifestError)return {status:'manifest-error'};
    if(holds[word]){status('재생 보류: '+word+' · '+holds[word].holdReason);return {status:'held',word}};
    if(records[word])return {status:'human-available'};
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
  // Mobile browsers can keep a tab alive while it is backgrounded: unlike a
  // BFCache restore, foregrounding it may fire only visibilitychange. A human
  // recording may have been withdrawn in the meantime, so never trust the old
  // manifest when a hidden tab becomes visible again.
  let wasHidden=false,resumeRefresh=null;
  function revalidateOnResume(){
    // A visibilitychange followed by pageshow.persisted must share one request.
    if(resumeRefresh)return resumeRefresh;
    resumeRefresh=reloadManifest().finally(()=>{resumeRefresh=null});
    return resumeRefresh;
  }
  document.addEventListener('visibilitychange',()=>{
    if(document.hidden){wasHidden=true;stop();return}
    if(wasHidden){wasHidden=false;void revalidateOnResume()}
  });
  window.addEventListener('pagehide',()=>{wasHidden=true;stop()});
  // Safari/Chrome may restore this page from the back-forward cache without
  // running the script again. Revalidate withdrawn recordings on that return;
  // never start playback automatically (a fresh tap is still required).
  window.addEventListener('pageshow',event=>{
    if(event.persisted){wasHidden=false;void revalidateOnResume()}
  });
  window.HSHangul={consonants,vowels,compose,records,ready,reloadManifest,availability,play,stop,status,el,soundButton,refreshBadges,canSynthesize,setSyntheticEnabled,optionalSynthetic};
})();
