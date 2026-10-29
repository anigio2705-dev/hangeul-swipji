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
