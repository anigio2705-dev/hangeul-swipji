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
  assert.equal((await H.play('다')).status,'tts-played','held recording is never played');
  assert.equal(calls.audio.length,1,'held audio URL must never be created');
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
