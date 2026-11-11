'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// Run with node; reads the actual application and never writes source files.
class Element {
  constructor(tag='div', text='') { this.tagName=tag.toUpperCase(); this.children=[]; this._text=text; this.value=''; this.dataset={}; this.childNodes=this.children; this.classList={toggle(){},add(){},remove(){}}; }
  get textContent(){ return this._text+this.children.map(x=>x.textContent).join(' '); }
  set textContent(v){ this._text=String(v); this.children.length=0; }
  append(...xs){ for(const x of xs){this.children.push(x);x.parentNode=this;} }
  prepend(...xs){this.children.unshift(...xs);}
  replaceChildren(...xs){this.children.length=0;this._text='';this.append(...xs);}
  setAttribute(k,v){this[k]=v;}
  showModal(){this.open=true;}
  close(){this.open=false;}
  addEventListener(){}
  removeEventListener(){}
  querySelector(){return null;}
  querySelectorAll(){return [];}
}
function descendants(root){return [root,...root.children.flatMap(descendants)];}
class FakeFormData {
  constructor(form){this.entries=descendants(form).filter(x=>x.name&&!x.disabled).map(x=>[x.name,String(x.value)]);}
  forEach(fn){this.entries.forEach(([k,v])=>fn(v,k));}
  get(k){return this.entries.find(x=>x[0]===k)?.[1]??null;}
  [Symbol.iterator](){return this.entries[Symbol.iterator]();}
}
const source=fs.readFileSync(path.join(process.cwd(),'phase3/app.js'),'utf8');
const end=source.lastIndexOf('})();');
assert.ok(end>0,'application IIFE must exist');
const exposed=source.slice(0,end)+'\nglobalThis.B84={state,discover,profile,bookings,bookingDialog,rescheduleDialog,formatZonedRange,localToUtc,admin,adminRescheduleDialog};\n'+source.slice(end);
function harness(deviceZone){
  const ids=new Map();
  const root=new Element();
  root.querySelector=s=>{if(!ids.has(s))ids.set(s,new Element());return ids.get(s);};
  root.querySelectorAll=()=>[];
  const document={querySelector:s=>s==='#studio-root'?{shadowRoot:root}:root.querySelector(s),createElement:t=>new Element(t),defaultView:{addEventListener(){},removeEventListener(){}}};
  const calls=[];
  let responder=()=>({});
  const NativeDTF=Intl.DateTimeFormat;
  function DTF(locale,options){return new NativeDTF(locale,{...options,timeZone:options?.timeZone||deviceZone});}
  DTF.supportedLocalesOf=NativeDTF.supportedLocalesOf.bind(NativeDTF);
  const context=vm.createContext({document,Node:Element,FormData:FakeFormData,URL,URLSearchParams,Intl:{DateTimeFormat:DTF,NumberFormat:Intl.NumberFormat},Date,console,location:{search:''},localStorage:{getItem(){return null;}},sessionStorage:{getItem(){return null;}},setInterval(){return 1;},clearInterval(){},fetch:async(url,opts)=>{
    // Startup is held at its first I/O, so it cannot race the independent tests.
    if(url==='/api/units')return new Promise(()=>{});
    calls.push({url:String(url),opts});return {ok:true,json:async()=>responder(String(url),opts)};
  }});
  vm.runInContext(exposed,context,{filename:'phase3/app.js'});
  return {api:context.B84,ids,calls,setResponse(fn){responder=fn;}};
}
const epoch=s=>Date.parse(s)/1000;
function rangeContains(value,zone,parts){
  assert.equal(typeof value,'string');
  assert.ok(value.includes(zone),'range must identify '+zone+': '+value);
  for(const part of parts)assert.ok(value.includes(part),'missing '+part+': '+value);
}
async function flush(){for(let i=0;i<25;i++)await Promise.resolve();}
function input(root,name){const n=descendants(root).find(x=>x.name===name);assert.ok(n,'missing input '+name);return n;}
async function submit(form){assert.equal(typeof form.onsubmit,'function');await form.onsubmit({preventDefault(){},currentTarget:form});await flush();}
async function main(){for(const device of ["UTC","Asia/Tokyo","America/Los_Angeles"]){const api=harness(device).api;for(const f of [{"zone": "Asia/Seoul", "local": "2026-01-01T09:00", "utc": "2026-01-01T00:00:00.000Z", "start": 1767225600.0, "end": 1767229200.0, "parts": ["09:00", "10:00", "+09:00"]}, {"zone": "Asia/Seoul", "local": "2026-03-08T16:30", "utc": "2026-03-08T07:30:00.000Z", "start": 1772955000.0, "end": 1772958600.0, "parts": ["16:30", "17:30", "+09:00"]}, {"zone": "Asia/Seoul", "local": "2026-11-01T16:30", "utc": "2026-11-01T07:30:00.000Z", "start": 1793518200.0, "end": 1793521800.0, "parts": ["16:30", "17:30", "+09:00"]}, {"zone": "America/New_York", "local": "2025-12-31T19:00", "utc": "2026-01-01T00:00:00.000Z", "start": 1767225600.0, "end": 1767229200.0, "parts": ["19:00", "20:00", "-05:00"]}, {"zone": "America/New_York", "local": "2026-03-08T03:30", "utc": "2026-03-08T07:30:00.000Z", "start": 1772955000.0, "end": 1772958600.0, "parts": ["03:30", "04:30", "-04:00"]}, {"zone": "America/New_York", "local": "2026-11-01T02:30", "utc": "2026-11-01T07:30:00.000Z", "start": 1793518200.0, "end": 1793521800.0, "parts": ["02:30", "03:30", "-05:00"]}, {"zone": "Asia/Kathmandu", "local": "2026-01-01T05:45", "utc": "2026-01-01T00:00:00.000Z", "start": 1767225600.0, "end": 1767229200.0, "parts": ["05:45", "06:45", "+05:45"]}, {"zone": "Asia/Kathmandu", "local": "2026-03-08T13:15", "utc": "2026-03-08T07:30:00.000Z", "start": 1772955000.0, "end": 1772958600.0, "parts": ["13:15", "14:15", "+05:45"]}, {"zone": "Asia/Kathmandu", "local": "2026-11-01T13:15", "utc": "2026-11-01T07:30:00.000Z", "start": 1793518200.0, "end": 1793521800.0, "parts": ["13:15", "14:15", "+05:45"]}, {"zone": "Pacific/Auckland", "local": "2026-01-01T13:00", "utc": "2026-01-01T00:00:00.000Z", "start": 1767225600.0, "end": 1767229200.0, "parts": ["13:00", "14:00", "+13:00"]}, {"zone": "Pacific/Auckland", "local": "2026-03-08T20:30", "utc": "2026-03-08T07:30:00.000Z", "start": 1772955000.0, "end": 1772958600.0, "parts": ["20:30", "21:30", "+13:00"]}, {"zone": "Pacific/Auckland", "local": "2026-11-01T20:30", "utc": "2026-11-01T07:30:00.000Z", "start": 1793518200.0, "end": 1793521800.0, "parts": ["20:30", "21:30", "+13:00"]}]){assert.equal(api.localToUtc(f.local,f.zone),f.utc);rangeContains(api.formatZonedRange(f.start,f.end,f.zone),f.zone,f.parts);}}
  const h=harness('UTC'), a=h.api;
  const start=epoch('2026-01-01T00:00:00Z'),endTime=start+3600;
  rangeContains(a.formatZonedRange(start,endTime,'Asia/Seoul'),'Asia/Seoul',['2026','09:00','10:00','+09:00']);
  rangeContains(a.formatZonedRange(start,endTime,'America/New_York'),'America/New_York',['2025','19:00','20:00','-05:00']);
  const spring=epoch('2026-03-08T06:30:00Z');
  rangeContains(a.formatZonedRange(spring,spring+3600,'America/New_York'),'America/New_York',['01:30','03:30','-05:00','-04:00']);
  const fall=epoch('2026-11-01T05:30:00Z');
  rangeContains(a.formatZonedRange(fall,fall+3600,'America/New_York'),'America/New_York',['01:30','-04:00','-05:00']);
  assert.equal(a.localToUtc('2026-01-01T05:45','Asia/Kathmandu'),'2026-01-01T00:00:00.000Z');
  assert.equal(a.localToUtc('2026-01-01T09:00','Asia/Seoul'),'2026-01-01T00:00:00.000Z');
  for(const value of ['2026-03-08T02:30','2026-11-01T01:30','2026-02-30T12:00','2026-01-01T25:00'])assert.throws(()=>a.localToUtc(value,'America/New_York'),undefined,value);
  assert.throws(()=>a.localToUtc('2026-01-01T09:00','Invalid/Nowhere'));
  const tokyo=harness('Asia/Tokyo').api;
  assert.equal(tokyo.formatZonedRange(start,endTime,'America/New_York'),a.formatZonedRange(start,endTime,'America/New_York'));
  assert.equal(tokyo.localToUtc('2026-01-01T05:45','Asia/Kathmandu'),a.localToUtc('2026-01-01T05:45','Asia/Kathmandu'));

  a.state.user={id:'learner',role:'learner',nickname:'Learner',timezone:'America/New_York'};
  a.state.units=[{id:'unit',level:'A0',title:'Unit'}];
  h.setResponse(()=>({teachers:[],total:0,hasMore:false}));
  const discover=new Element();await a.discover(discover);
  assert.ok(discover.textContent.includes('America/New_York'),'search must name profile zone');
  const searchForm=descendants(discover).find(x=>x.tagName==='FORM');
  for(const value of ['2026-03-08T02:30','2026-11-01T01:30']){
    input(searchForm,'from').value=value;input(searchForm,'to').value='2026-11-02T12:00';
    h.calls.length=0;await submit(searchForm);
    assert.equal(h.calls.length,0,'invalid search must not call API');
    assert.ok(h.ids.get('#message').textContent.length>0,'DST rejection must explain error');
  }
  input(searchForm,'from').value='2026-01-01T19:00';input(searchForm,'to').value='2026-01-01T20:00';
  h.calls.length=0;await submit(searchForm);
  assert.equal(h.calls.length,1);
  assert.equal(new URL(h.calls[0].url,'http://test.invalid').searchParams.get('from'),'2026-01-02T00:00:00.000Z');

  const slot={id:'original-slot',start,end:endTime};
  const teacher={id:'teacher',nickname:'Teacher',timezone:'Asia/Seoul',price:20000};
  h.setResponse(()=>({slots:[slot]}));
  await a.bookingDialog(teacher);
  const detail=h.ids.get('#detail');
  rangeContains(detail.textContent,'Asia/Seoul',['09:00','10:00','+09:00']);
  rangeContains(detail.textContent,'America/New_York',['19:00','20:00','-05:00']);
  assert.equal(input(detail,'slotId').value,'original-slot');
  assert.deepEqual(slot,{id:'original-slot',start,end:endTime},'display must not mutate UTC slot');
  const booking={id:'abc',learner_id:'learner',teacher_id:'teacher',unit_id:'unit',status:'test_paid',price:20000,slot,learnerTimezone:'America/New_York',teacherTimezone:'Asia/Seoul'};
  await a.rescheduleDialog(booking);
  rangeContains(detail.textContent,'Asia/Seoul',['09:00','10:00','+09:00']);
  rangeContains(detail.textContent,'America/New_York',['19:00','20:00','-05:00']);
  assert.equal(input(detail,'slotId').value,'original-slot');
  h.setResponse(()=>({bookings:[booking]}));
  const lessons=new Element();await a.bookings(lessons);
  rangeContains(lessons.textContent,'Asia/Seoul',['09:00','10:00','+09:00']);
  rangeContains(lessons.textContent,'America/New_York',['19:00','20:00','-05:00']);

  a.state.user={...teacher,role:'teacher',approved:true,timezone:'America/New_York'};
  h.setResponse(url=>url.startsWith('/api/earnings')?{teacherAccrued:0,referralAccrued:0,entries:[]}:{slots:[]});
  const profile=new Element();await a.profile(profile);
  const availability=descendants(profile).find(x=>x.tagName==='FORM'&&descendants(x).some(y=>y.name==='start'));
  assert.ok(availability,'availability form exists');
  assert.ok(profile.textContent.includes('America/New_York'));
  for(const value of ['2026-03-08T02:30','2026-11-01T01:30']){
    input(availability,'start').value=value;input(availability,'end').value='2026-11-02T12:00';
    h.calls.length=0;await submit(availability);
    assert.equal(h.calls.length,0,'invalid availability must not call API');
    assert.ok(h.ids.get('#message').textContent.length>0);
  }
  a.state.user={...teacher,role:'learner',timezone:''};
  h.setResponse(()=>({teachers:[],total:0,hasMore:false}));
  const fallback=new Element();await a.discover(fallback);
  assert.ok(fallback.textContent.includes('UTC'),'empty profile must identify device fallback');
  assert.match(fallback.textContent,/기기|대체|fallback|device/i,'fallback must be disclosed');
}
main().catch(error=>{console.error(error);process.exitCode=1;});


async function adminParticipantZoneRegression(){
  const h=harness('Pacific/Honolulu'), a=h.api;
  assert.equal(typeof a.admin,'function','host must expose admin in B84');
  assert.equal(typeof a.adminRescheduleDialog,'function','host must expose adminRescheduleDialog in B84');
  a.state.user={id:'operator',role:'admin',nickname:'Operator',timezone:'Europe/Paris'};
  const users=[
    {id:'student-84',nickname:'Student',role:'learner',timezone:'America/New_York'},
    {id:'teacher-84',nickname:'Teacher',role:'teacher',approved:true,timezone:'Asia/Seoul'}
  ];
  const booking={id:'booking-84',learner_id:'student-84',teacher_id:'teacher-84',unit_id:'unit-84',status:'test_paid',price:20000};
  const dispute={id:'dispute-84',booking_id:booking.id,status:'open',category:'connection',reason:'Independent regression'};
  const slot={id:'replacement-84',start:epoch('2026-03-08T06:30:00Z'),end:epoch('2026-03-08T07:30:00Z')};
  assert.ok(!('learnerTimezone' in booking)&&!('teacherTimezone' in booking)&&!('timezone' in booking));
  h.setResponse((url,opts)=>{
    assert.equal(opts.method,'GET','regression must only read fake API data');
    if(url==='/api/admin')return {users,bookings:[booking],disputes:[dispute],ledger:[],audit:[]};
    if(url==='/api/availability?teacherId=teacher-84')return {slots:[slot]};
    throw Error('Unexpected API request: '+url);
  });
  const root=new Element();
  await a.admin(root);
  const actions=descendants(root).filter(n=>n.tagName==='BUTTON'&&n.textContent==='합의된 재수업');
  assert.equal(actions.length,1,'actual admin UI must expose reschedule action');
  actions[0].onclick();
  await flush();
  assert.deepEqual(h.calls.map(c=>c.url),['/api/admin','/api/availability?teacherId=teacher-84']);
  assert.equal(h.ids.get('#detail-dialog')?.open,true,'admin action must open dialog');
  const detail=h.ids.get('#detail');
  assert.ok(detail,'admin dialog content must exist');
  const select=input(detail,'slotId');
  assert.equal(select.value,slot.id);
  const options=descendants(select).filter(n=>n.tagName==='OPTION');
  assert.equal(options.length,1);
  const text=options[0].textContent;
  assert.ok(text.includes('학습자: 2026-03-08 01:30:00 America/New_York UTC-05:00 ~ 2026-03-08 03:30:00 America/New_York UTC-04:00'),text);
  assert.ok(text.includes('강사: 2026-03-08 15:30:00 Asia/Seoul UTC+09:00 ~ 2026-03-08 16:30:00 Asia/Seoul UTC+09:00'),text);
  assert.ok(!/Pacific\/Honolulu|Europe\/Paris|기기 시간대 대체/.test(text),'must use participant zones, not device/admin fallback');
  assert.equal(h.ids.get('#message')?.textContent||'','','UI action must not swallow an error');
}
adminParticipantZoneRegression().catch(error=>{console.error(error);process.exitCode=1;});
