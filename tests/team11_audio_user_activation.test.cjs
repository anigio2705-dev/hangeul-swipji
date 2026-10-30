/* Regression: mobile Audio.play must be called before the first await when the manifest is already loaded.
 * Run: node --test tests/team11_audio_user_activation.test.cjs
 * No network, real audio files, or browser needed. Real-device validation is separate.
 */
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'..','hangul-core.js'),'utf8');
test('loaded manifest allows synchronous Audio.play from click handler',async()=>{
  let resolveFetch;
  const fetchPromise=new Promise(r=>resolveFetch=r);
  const events={};const clicks=[];const attrs={};
  const document={
    baseURI:'https://example.test/hangul-basics.html',
    addEventListener:(name,fn)=>{events[name]=fn},
    dispatchEvent:()=>{},
    querySelectorAll:()=>[],
    querySelector:()=>null,
    createElement:(tag)=>({tagName:tag,classList:{toggle(){}},dataset:{},setAttribute(k,v){attrs[k]=v}}),
  };
  class AudioMock{
    constructor(url){this.url=url;this.onended=null;this.onerror=null;this.onplaying=null}
    play(){clicks.push({url:this.url,insideClick});if(this.onplaying)this.onplaying();if(this.onended)this.onended();return Promise.resolve()}
    pause(){}
  }
  let insideClick=false;
  const context={document,window:{addEventListener(){},speechSynthesis:{cancel(){}}},Audio:AudioMock,URL,Event:class{},setTimeout,clearTimeout,
    fetch:()=>fetchPromise};
  vm.runInNewContext(source,context);
  resolveFetch({ok:true,json:async()=>({recordings:{'가':{kind:'human',src:'./assets/hangul-audio/ac00-r2.mp3',sha256:'a'.repeat(64),sourceUrl:'https://commons.wikimedia.org/wiki/File:Ko.mp3',author:'speaker',license:'CC-BY'}}})});
  await context.window.HSHangul.ready;
  insideClick=true;
  const result=context.window.HSHangul.play('가');
  insideClick=false;
  assert.equal(clicks.length,1,'Audio.play must start synchronously while click activation exists');
  assert.equal(clicks[0].insideClick,true);
  assert.match(clicks[0].url,/ac00-r2.mp3\?v=aaaaaaaaaaaaaaaa/);
  assert.equal((await result).status,'played');
});
test('missing human recording does not synthesize or create Audio',async()=>{
  const context={document:{baseURI:'https://example.test/',addEventListener(){},dispatchEvent(){},querySelectorAll:()=>[],querySelector:()=>null},window:{addEventListener(){},speechSynthesis:{cancel(){}}},Event:class{},URL,setTimeout,clearTimeout,Audio:class{constructor(){throw Error('unexpected Audio')}} ,fetch:async()=>({ok:true,json:async()=>({recordings:{}})})};
  vm.runInNewContext(source,context);await context.window.HSHangul.ready;
  const result=await context.window.HSHangul.play('기역');
  assert.equal(result.status,'missing');
});

test('TTS is opt-in, human-first, and never plays a held human asset',async()=>{
  const calls={audio:[],speak:[],cancel:0};
  const records={
    '가':{kind:'human',src:'./assets/hangul-audio/ac00-r2.mp3',sha256:'a'.repeat(64),sourceUrl:'https://commons.wikimedia.org/wiki/File:A',author:'speaker',license:'CC-BY'},
    '다':{kind:'human',disabled:true,holdReason:'발음 검수 보류',src:'./assets/hangul-audio/b2e4.mp3',sha256:'b'.repeat(64),sourceUrl:'https://commons.wikimedia.org/wiki/File:B',author:'speaker2',license:'CC-BY'},
  };
  class AudioMock{
    constructor(src){calls.audio.push(src)}
    play(){this.onplaying?.();this.onended?.();return Promise.resolve()}
    pause(){}
  }
  class UtteranceMock{constructor(text){this.text=text}}
  const synth={cancel(){calls.cancel++},speak(u){calls.speak.push({word:u.text,lang:u.lang});u.onstart?.();u.onend?.()}};
  const document={baseURI:'https://example.test/hangul-basics.html',addEventListener(){},dispatchEvent(){},
    querySelectorAll:()=>[],querySelector:()=>null};
  const context={document,URL,Audio:AudioMock,Event:class{},setTimeout,clearTimeout,
    window:{addEventListener(){},speechSynthesis:synth,SpeechSynthesisUtterance:UtteranceMock},
    fetch:async()=>({ok:true,json:async()=>({recordings:records})})};
  vm.runInNewContext(source,context);
  const H=context.window.HSHangul;
  await H.ready;
  assert.equal((await H.play('나')).status,'missing','without explicit consent no synthesis');
  assert.equal(calls.speak.length,0);
  H.setSyntheticEnabled(true);
  assert.equal((await H.play('나')).status,'tts-played','missing sound can use opt-in device voice');
  assert.equal(calls.speak[0].word,'나');
  assert.equal(calls.speak[0].lang,'ko-KR');
  assert.equal((await H.play('가')).status,'played','human recording wins over synthetic');
  assert.equal(calls.audio.length,1);
  assert.match(calls.audio[0],/ac00-r2\.mp3/);
  assert.equal((await H.play('다')).status,'held','review hold blocks even opted-in TTS');
  assert.equal(calls.audio.length,1,'held audio URL must never be created');
  assert.equal(calls.speak.length,1,'review hold must not synthesize either');
  H.setSyntheticEnabled(false);
  assert.equal((await H.play('다')).status,'held');
  const cancelsBefore=calls.cancel;
  H.setSyntheticEnabled(true);
  assert.ok(calls.cancel>cancelsBefore,'enabling TTS also cancels an older playback');
  H.setSyntheticEnabled(false);
});

test('cancelled synthetic completion cannot release a newer playback',async()=>{
  const spoken=[];
  const synth={cancel(){},speak(u){spoken.push(u);u.onstart?.()}};
  const context={
    document:{baseURI:'https://example.test/',addEventListener(){},dispatchEvent(){},querySelectorAll:()=>[],querySelector:()=>null},
    window:{addEventListener(){},speechSynthesis:synth,SpeechSynthesisUtterance:class{constructor(t){this.text=t}}},
    Event:class{},URL,setTimeout,clearTimeout,
    Audio:class{pause(){} play(){return Promise.resolve()}},
    fetch:async()=>({ok:true,json:async()=>({recordings:{}})})
  };
  vm.runInNewContext(source,context);
  const H=context.window.HSHangul;await H.ready;H.setSyntheticEnabled(true);
  const first=H.play('나');
  await Promise.resolve();
  const second=H.play('다');
  await Promise.resolve();
  spoken[0]?.onend?.(); // a stale callback after cancellation
  H.stop();
  assert.equal((await first).status,'cancelled');
  assert.equal((await second).status,'cancelled');
});

test('board distinguishes TTS errors, cancellation, and manifest failures',()=>{
  const board=fs.readFileSync(path.join(__dirname,'..','hangul-board.js'),'utf8');
  assert.match(board,/result\.status\?\.startsWith\('tts-'\)/);
  assert.match(board,/result\.status==='cancelled'/);
  assert.match(board,/result\.status==='manifest-error'/);
  assert.match(board,/result\.status==='held'/);
  assert.match(board,/result\.status==='missing'/);
  assert.match(board,/result\.status==='tts-played'/);
});

test('early mobile tap does not attempt playback after manifest await; retry stays inside tap',async()=>{
  let deliver;
  const pending=new Promise(resolve=>{deliver=resolve});
  let insideClick=false;
  const calls=[];
  const context={
    document:{baseURI:'https://example.test/hangul-basics.html',addEventListener(){},dispatchEvent(){},querySelectorAll:()=>[],querySelector:()=>null},
    window:{addEventListener(){},speechSynthesis:{cancel(){}}},
    Audio:class{
      constructor(url){this.url=url}
      play(){calls.push({url:this.url,insideClick});this.onended?.();return Promise.resolve()}
      pause(){}
    },
    URL,Event:class{},setTimeout,clearTimeout,fetch:()=>pending
  };
  vm.runInNewContext(source,context);
  const H=context.window.HSHangul;
  insideClick=true;
  const first=H.play('가');
  insideClick=false;
  assert.equal((await first).status,'loading');
  assert.equal(calls.length,0,'must not queue autoplay after async manifest fetch');
  deliver({ok:true,json:async()=>({recordings:{'가':{
    kind:'human',src:'./assets/hangul-audio/ac00-r2.mp3',
    sha256:'a'.repeat(64),sourceUrl:'https://example.test/recording',
    author:'speaker',license:'CC-BY'
  }}})});
  await H.ready;
  insideClick=true;
  const second=H.play('가');
  insideClick=false;
  assert.equal(calls.length,1);
  assert.equal(calls[0].insideClick,true,'Audio.play must start during fresh user activation');
  assert.equal((await second).status,'played');
});
test('failed manifest requests are retried without delayed autoplay',async()=>{
  let requests=0;
  const manifest={recordings:{}};
  const context={
    document:{baseURI:'https://example.test/',addEventListener(){},dispatchEvent(){},querySelectorAll:()=>[],querySelector:()=>null},
    window:{addEventListener(){},speechSynthesis:{cancel(){}}},
    Audio:class{constructor(){throw Error('must not create Audio')}},
    URL,Event:class{},setTimeout,clearTimeout,
    fetch:()=>{requests++;return requests===1?Promise.reject(Error('offline')):Promise.resolve({ok:true,json:async()=>manifest})}
  };
  vm.runInNewContext(source,context);
  const H=context.window.HSHangul;
  await H.ready;
  assert.equal((await H.play('가')).status,'manifest-error');
  assert.equal(requests,2,'fresh tap initiates one manifest retry');
  // Retry request is asynchronous; no Audio should be started from its completion.
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal((await H.play('가')).status,'missing');
});

test('manifest refresh revokes stale playable badges and refuses taps until the new inventory arrives',async()=>{
  const human={kind:'human',src:'./assets/hangul-audio/ac00-r2.mp3',sha256:'a'.repeat(64),
    sourceUrl:'https://example.test/recording',author:'speaker',license:'CC-BY'};
  let refreshResponse,requests=0,created=0;
  const badge={dataset:{sound:'가'},classList:{toggle(){}},setAttribute(){}};
  const context={
    document:{baseURI:'https://example.test/hangul-basics.html',addEventListener(){},dispatchEvent(){},
      querySelectorAll(selector){return selector==='[data-sound]'?[badge]:[]},querySelector:()=>null},
    window:{addEventListener(){},speechSynthesis:{cancel(){}}},
    Audio:class{constructor(){created++}play(){throw Error('stale audio must not play')}pause(){}},
    URL,Event:class{},setTimeout,clearTimeout,
    fetch:()=>{
      requests++;
      if(requests===1)return Promise.resolve({ok:true,json:async()=>({recordings:{'가':human}})});
      return new Promise(resolve=>{refreshResponse=resolve});
    }
  };
  vm.runInNewContext(source,context);
  const H=context.window.HSHangul;
  await H.ready;
  assert.equal(H.availability('가').state,'ready');
  const pending=H.reloadManifest();
  assert.equal(requests,2);
  assert.equal(H.availability('가').state,'unavailable','old audio must not appear playable during refresh');
  assert.equal(badge.dataset.audioState,'unavailable','badge must update before the network reply');
  assert.equal((await H.play('가')).status,'loading','tap during refresh must not play stale audio');
  assert.equal(created,0);
  refreshResponse({ok:true,json:async()=>({recordings:{}})});
  assert.equal((await pending).status,'ready');
  assert.equal(H.availability('가').state,'missing','withdrawn recording must stay unavailable');
  assert.equal((await H.play('가')).status,'missing');
  assert.equal(created,0);
});

test('mobile BFCache restore revalidates audio without autoplay or duplicate initial fetch',async()=>{
  const handlers={};let requests=0,deliver,created=0;
  const record={kind:'human',src:'./assets/hangul-audio/ac00-r2.mp3',sha256:'a'.repeat(64),
    sourceUrl:'https://example.test/recording',author:'speaker',license:'CC-BY'};
  const context={
    document:{baseURI:'https://example.test/hangul-week.html',hidden:false,addEventListener(){},dispatchEvent(){},
      querySelectorAll:()=>[],querySelector:()=>null},
    window:{addEventListener(name,fn){handlers[name]=fn},speechSynthesis:{cancel(){}}},
    Audio:class{constructor(){created++}play(){throw Error('BFCache must not autoplay')}pause(){}},
    URL,Event:class{},setTimeout,clearTimeout,
    fetch:()=>{
      requests++;
      if(requests===1)return Promise.resolve({ok:true,json:async()=>({recordings:{'가':record}})});
      return new Promise(resolve=>{deliver=resolve});
    }
  };
  vm.runInNewContext(source,context);
  const H=context.window.HSHangul;await H.ready;
  assert.equal(H.availability('가').state,'ready');
  handlers.pageshow({persisted:false});
  assert.equal(requests,1,'initial pageshow must not duplicate the initial manifest request');
  handlers.pagehide();
  handlers.pageshow({persisted:true});
  assert.equal(requests,2,'restored pages must request a fresh manifest');
  assert.equal(H.availability('가').state,'unavailable','BFCache must not expose a stale recording');
  assert.equal((await H.play('가')).status,'loading');
  assert.equal(created,0,'restore must never autoplay audio');
  deliver({ok:true,json:async()=>({recordings:{}})});
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(H.availability('가').state,'missing');
  assert.equal(created,0);
});


test('mobile tab foreground revalidates withdrawn audio and coalesces BFCache resume',async()=>{
  const windowHandlers={},documentHandlers={};
  let requests=0,deliver,created=0;
  const human={kind:'human',src:'./assets/hangul-audio/ac00-r2.mp3',sha256:'a'.repeat(64),
    sourceUrl:'https://example.test/recording',author:'speaker',license:'CC-BY'};
  const document={
    baseURI:'https://example.test/hangul-basics.html',hidden:false,
    addEventListener(name,fn){documentHandlers[name]=fn},
    dispatchEvent(){},querySelectorAll:()=>[],querySelector:()=>null
  };
  const context={document,URL,Event:class{},setTimeout,clearTimeout,
    window:{addEventListener(name,fn){windowHandlers[name]=fn},speechSynthesis:{cancel(){}}},
    Audio:class{constructor(){created++}play(){throw Error('background audio must not autoplay')}pause(){}},
    fetch:()=>{
      requests++;
      if(requests===1)return Promise.resolve({ok:true,json:async()=>({recordings:{'가':human}})});
      return new Promise(resolve=>{deliver=resolve});
    }
  };
  vm.runInNewContext(source,context);
  const H=context.window.HSHangul;await H.ready;
  assert.equal(H.availability('가').state,'ready');
  document.hidden=true;
  documentHandlers.visibilitychange();
  document.hidden=false;
  documentHandlers.visibilitychange();
  assert.equal(requests,2,'foreground must revalidate stale audio even without pagehide');
  assert.equal(H.availability('가').state,'unavailable','foreground must revoke old audio immediately');
  assert.equal((await H.play('가')).status,'loading');
  windowHandlers.pageshow({persisted:true});
  assert.equal(requests,2,'BFCache pageshow must share the pending foreground refresh');
  assert.equal(created,0,'neither foreground nor BFCache can autoplay');
  deliver({ok:true,json:async()=>({recordings:{}})});
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(H.availability('가').state,'missing','withdrawn audio must remain blocked');
  assert.equal(created,0);
});


test('manual refresh queued during initial fetch must never expose the first manifest to a mobile tap',async()=>{
  const human={kind:'human',src:'./assets/hangul-audio/ac00-r2.mp3',sha256:'a'.repeat(64),
    sourceUrl:'https://example.test/recording',author:'speaker',license:'CC-BY'};
  let deliverInitial,deliverRefresh,requests=0,created=0,H,seenState,attempt,ttsAttempt,synthCalls=0;
  const document={
    baseURI:'https://example.test/hangul-basics.html',
    addEventListener(){},querySelectorAll:()=>[],querySelector:()=>null,
    dispatchEvent(){
      // The first response must remain untrusted: a newer refresh was requested
      // while it was pending. An actual mobile tap may happen in this callback.
      if(requests===1){
        seenState=H.availability('가').state;
        attempt=H.play('가');
        ttsAttempt=H.optionalSynthetic('나');
      }
    }
  };
  const context={document,URL,Event:class{},setTimeout,clearTimeout,
    window:{addEventListener(){},speechSynthesis:{cancel(){},speak(u){synthCalls++;u.onend?.()}},SpeechSynthesisUtterance:class{constructor(text){this.text=text}}},
    Audio:class{constructor(){created++}play(){this.onended?.();return Promise.resolve()}pause(){}},
    fetch:()=>{
      requests++;
      return new Promise(resolve=>{
        if(requests===1)deliverInitial=resolve;
        else deliverRefresh=resolve;
      });
    }
  };
  vm.runInNewContext(source,context);
  H=context.window.HSHangul;
  H.setSyntheticEnabled(true);
  const refresh=H.reloadManifest();
  deliverInitial({ok:true,json:async()=>({recordings:{'가':human}})});
  await H.ready;
  assert.equal(seenState,'unavailable','first manifest cannot reopen audio while manual refresh is queued');
  assert.equal((await attempt).status,'loading','tap cannot start stale recording');
  assert.equal((await ttsAttempt).status,'loading','direct optional TTS must also wait for the new manifest');
  assert.equal(synthCalls,0,'no device speech while a newer manifest is queued');
  assert.equal(created,0,'Audio constructor must not run during the queued refresh');
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(requests,2);
  deliverRefresh({ok:true,json:async()=>({recordings:{}})});
  assert.equal((await refresh).status,'ready');
  assert.equal(H.availability('가').state,'missing');
  assert.equal(created,0);
});


test('direct optional TTS reports cancelled when mobile pagehide cancels speech synchronously',async()=>{
  let activeUtterance=null,spoken=0,cancellations=0;
  const handlers={};
  const context={
    document:{baseURI:'https://example.test/hangul-basics.html',hidden:false,
      addEventListener(){},dispatchEvent(){},querySelectorAll:()=>[],querySelector:()=>null},
    window:{addEventListener(name,fn){handlers[name]=fn},
      SpeechSynthesisUtterance:class{constructor(text){this.text=text}},
      speechSynthesis:{
        speak(utterance){spoken++;activeUtterance=utterance},
        cancel(){
          cancellations++;
          // Some browsers synchronously emit onend during cancel().
          // This is NOT a successful pronunciation.
          if(activeUtterance){const u=activeUtterance;activeUtterance=null;u.onend?.()}
        }
      }
    },
    Audio:class{constructor(){throw Error('no human recording expected')}},
    URL,Event:class{},setTimeout,clearTimeout,
    fetch:async()=>({ok:true,json:async()=>({recordings:{}})})
  };
  vm.runInNewContext(source,context);
  const H=context.window.HSHangul;await H.ready;
  H.setSyntheticEnabled(true);
  const pending=H.optionalSynthetic('나');
  assert.equal(spoken,1,'TTS must actually start before cancellation');
  handlers.pagehide();
  assert.equal((await pending).status,'cancelled',
    'browser onend emitted by cancel() must not report synthetic playback success');
  assert.equal(cancellations>=2,true);
});


test('backgrounded mobile page rejects new human and optional TTS playback until restored',async()=>{
  const handlers={};let audioStarts=0,ttsStarts=0;
  const human={kind:'human',src:'./assets/hangul-audio/ac00-r2.mp3',
    sha256:'a'.repeat(64),sourceUrl:'https://example.test/recording',
    author:'speaker',license:'CC-BY'};
  const document={baseURI:'https://example.test/hangul-basics.html',hidden:false,
    addEventListener(){},dispatchEvent(){},querySelectorAll:()=>[],querySelector:()=>null};
  const context={
    document,URL,Event:class{},setTimeout,clearTimeout,
    window:{addEventListener(name,fn){handlers[name]=fn},
      SpeechSynthesisUtterance:class{constructor(text){this.text=text}},
      speechSynthesis:{cancel(){},speak(u){ttsStarts++;u.onend?.()}}},
    Audio:class{play(){audioStarts++;this.onended?.();return Promise.resolve()}pause(){}},
    fetch:async()=>({ok:true,json:async()=>({recordings:{'가':human}})})
  };
  vm.runInNewContext(source,context);
  const H=context.window.HSHangul;await H.ready;
  handlers.pagehide();
  assert.equal((await H.play('가')).status,'cancelled',
    'a stale tap handler must not start human audio after pagehide');
  H.setSyntheticEnabled(true);
  assert.equal((await H.optionalSynthetic('나')).status,'cancelled',
    'optional TTS must not start after pagehide');
  assert.equal(audioStarts,0);
  assert.equal(ttsStarts,0);
  document.hidden=true;
  assert.equal((await H.play('가')).status,'cancelled',
    'hidden document must not start audio even without a pagehide event');
});


test('P0 independent QA: opt-in synthetic timeout is never a successful pronunciation when browser cancel fires onend synchronously',async()=>{
  let timeoutCallback, activeUtterance=null, speakCount=0, cancelCount=0;
  const context={
    document:{baseURI:'https://example.test/hangul-basics.html',hidden:false,
      addEventListener(){},dispatchEvent(){},querySelectorAll:()=>[],querySelector:()=>null},
    window:{addEventListener(){},
      SpeechSynthesisUtterance:class{constructor(text){this.text=text}},
      speechSynthesis:{
        speak(u){speakCount++;activeUtterance=u},
        cancel(){
          cancelCount++;
          if(activeUtterance){
            const old=activeUtterance;activeUtterance=null;
            old.onend?.(); // Safari/Chrome can deliver onend synchronously on cancel
          }
        }
      }
    },
    Audio:class{constructor(){throw Error('no human audio expected')}},
    URL,Event:class{},
    setTimeout(fn,ms){if(ms===12000){timeoutCallback=fn;return 12000}return 15000},
    clearTimeout(){},
    fetch:async()=>({ok:true,json:async()=>({recordings:{}})})
  };
  vm.runInNewContext(source,context);
  const H=context.window.HSHangul;
  await H.ready;
  H.setSyntheticEnabled(true);
  const pending=H.optionalSynthetic('나');
  assert.equal(speakCount,1,'opt-in synthetic playback must have actually started');
  assert.equal(typeof timeoutCallback,'function','timeout protection must be installed');
  timeoutCallback();
  assert.equal((await pending).status,'tts-timeout',
    'a timed-out and cancelled synthetic utterance must never be marked tts-played');
  assert.ok(cancelCount>=2,'timed-out speech must be cancelled');
});
