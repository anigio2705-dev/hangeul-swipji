/* Source and invariant checks. Passing is NOT a human pronunciation or learner trial. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),vm=require('node:vm'),cp=require('node:child_process');
const {root,courses,lessons,reading}=require('./curriculum-source.cjs');
const baseline='46745d28b17554f7d0f67e3e5515778b7ccb35e3';
const report={baseline,scope:'automated source checks; AI teaching review is recorded separately',generatedAt:new Date().toISOString(),errors:[],warnings:[],lessons:{units:0,questions:0,pairGroundedQuestions:0,mechanicallyGroundedQuestions:0,otherQuestions:0,examples:0,vocabularyEntries:0,placeholderNotes:0,otherQuestionSources:[]},reading:{items:0,questions:0,languages:2,exactDuplicates:0,levels:[],entries:[]},audio:{},preservation:{}};
const check=(ok,message)=>{if(!ok)report.errors.push(message)};
const norm=s=>String(s).normalize('NFC').replace(/[“”‘’]/g,"'").replace(/\s+/g,' ').trim().replace(/[.!?]+$/,'').toLowerCase();
const C=[...'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'],V=[...'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ'],F=['',...'ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ'];
function parts(s){const n=s.codePointAt(0)-0xac00;if(n<0||n>=11172)return null;return [C[Math.floor(n/588)],V[Math.floor(n/28)%21],F[n%28]]}
for(const name of courses){
 const units=lessons(name),old=JSON.parse(cp.execFileSync('git',['show',baseline+':'+name+'.html'],{cwd:root,encoding:'utf8'}).match(/const units=(\[.*?\]);/s)[1]);
 check(units.length===old.length,name+' lost units');
 units.forEach((u,i)=>{
  const id=name+'/'+(i+1),pairs=[...u.v,...u.sent];report.lessons.units++;report.lessons.examples+=u.sent.length;report.lessons.vocabularyEntries+=u.v.length;
  check(u.quiz.length===old[i].quiz.length,id+' lost quiz slots');check(u.sent.length>=old[i].sent.length,id+' lost examples');
  for(const pair of [...pairs,...u.grammar])check(pair.length===2&&pair.every(x=>typeof x==='string'&&x.trim()),id+' malformed bilingual pair');
  if(u.grammar.some(p=>/構造|構文|분석하고 관련 표현을 비교하세요|핵심 표현 .*문맥 속에서 익히고 문장/.test(p[0])))report.lessons.placeholderNotes++;
  u.quiz.forEach((q,j)=>{
   const tag=id+'/Q'+(j+1);report.lessons.questions++;check(new Set(q[2].map(norm)).size===q[2].length,tag+' duplicate choices');
   check(Number.isInteger(q[3])&&q[3]>=0&&q[3]<q[2].length,tag+' invalid answer');
   let expected=null;const prompt=q[0];
   // Independently cross-check translation/vocabulary questions against their source pairs.
   if(/의 뜻은\?|문장의 의미를 고르세요|다음 문장의 뜻은|문장을 이해한 내용|문장의 핵심 의미/.test(prompt)&&!/에서 ['‘]/.test(prompt)){
    const match=pairs.filter(p=>prompt.includes(p[0])).sort((a,b)=>b[0].length-a[0].length)[0];if(match)expected=match[1];
   }else if(/한국어 표현은\?|영어에 해당하는 한국어는|맞는 표현은|한국어로\?|맞는 문장은|해당하는 문장은|영어 표현에 맞는 한국어 문장은|단원의 중심 표현은/.test(prompt)){
    const match=pairs.filter(p=>prompt.includes(p[1])).sort((a,b)=>b[1].length-a[1].length)[0];if(match)expected=match[0];
   }
   if(expected!==null){
    const matches=q[2].map((x,k)=>norm(x)===norm(expected)?k:-1).filter(k=>k>=0);
    check(matches.length===1&&matches[0]===q[3],tag+' pair/answer mismatch: '+expected);report.lessons.pairGroundedQuestions++;return;
   }
   if(name==='intro'){
    const quoted=prompt.match(/[‘']([^’']+)[’']/)?.[1];const p=quoted&&parts(quoted);
    if(prompt.includes(' + ')&&prompt.includes('=')){
     const letters=prompt.split('=')[0].trim().split(/\s*\+\s*/);if(letters.length>=2&&C.includes(letters[0])&&V.includes(letters[1]))expected=String.fromCharCode(0xac00+(C.indexOf(letters[0])*21+V.indexOf(letters[1]))*28+(letters[2]?F.indexOf(letters[2]):0));
    }else if(p&&/모음은/.test(prompt))expected=p[1];
    else if(p&&/자음은|첫 자음은/.test(prompt))expected=p[0];
    else if(p&&/받침은/.test(prompt))expected=p[2];
    else if(p&&/받침을 빼면/.test(prompt))expected=String.fromCharCode(quoted.codePointAt(0)-(quoted.codePointAt(0)-0xac00)%28);
    else if(quoted&&/몇 글자|몇 음절/.test(prompt))expected=String([...quoted].length);
    else if(quoted&&/첫 글자/.test(prompt))expected=[...quoted][0];
    else if(p&&/구성하는 글자/.test(prompt))expected=p.filter(Boolean).join(' + ');
   }
   if(expected!==null){check(norm(q[2][q[3]])===norm(expected),tag+' Hangul answer mismatch');report.lessons.mechanicallyGroundedQuestions++}
   else {report.lessons.otherQuestions++;report.lessons.otherQuestionSources.push({id:tag,prompt:q[0],answer:q[2][q[3]],options:q[2]});}
  });
 });
}
check(report.lessons.units===350&&report.lessons.questions===1758,'Curriculum counts');check(report.lessons.placeholderNotes===0,'Placeholder notes remain');
const ko=reading('ko'),en=reading('en'),seen=new Map();
for(let l=1;l<=15;l++){
 const counts=[],lengths=[],vocab=new Set();
 for(let b=1;b<=40;b++){
  const id=l+'-'+b,x=ko.get(l,b),y=en.get(l,b),text=x.paragraphs.join(' ');report.reading.items++;report.reading.questions+=x.q.length;
  check(x.paragraphs.length===l+2,id+' unexpected graded sentence count');
  check(x.paragraphs.length===x.translations.length&&x.translations.every(t=>typeof t==='string'&&t.trim()),id+' translation alignment');
  check(JSON.stringify(x.paragraphs)===JSON.stringify(y.paragraphs)&&JSON.stringify(x.translations)===JSON.stringify(y.translations),id+' language toggling changes source');
  if(seen.has(text)){report.reading.exactDuplicates++;report.errors.push('Duplicate passage '+id+' and '+seen.get(text))}seen.set(text,id);
  for(const [k,q] of x.q.entries()){
   check(q.evidence&&text.includes(q.evidence),id+' missing Q'+k+' evidence');
   check(q.options.length===4&&new Set(q.options).size===4,id+' duplicate options');
   check(q.correct>=0&&q.correct<4,id+' invalid key');
   const e=y.q[k];check(new Set(e.options).size===4&&e.options.every(Boolean),id+' English choices');
   if(k>0){check(x.paragraphs.filter(p=>p===q.options[q.correct]).length===1,id+' nonunique Korean support');check(x.paragraphs.filter(p=>q.options.includes(p)).length===1,id+' distractor also occurs');check(y.translations.filter(p=>e.options.includes(p)).length===1,id+' English distractor also occurs')}
  }
  check(x.legacy.paragraphs.length>0&&x.legacy.translations.length===x.legacy.paragraphs.length,id+' legacy source lost');
  const words=text.split(/\s+/);counts.push(words.length);for(const p of x.paragraphs)lengths.push(p.split(/\s+/).length);words.forEach(w=>vocab.add(w));
  report.reading.entries.push({id,sentences:x.paragraphs.length,eojeol:words.length,questions:x.q.length,translationPairs:x.translations.length,sourceFamily:x.sourceFamily,legacyPreserved:true,sourceSha256:crypto.createHash('sha256').update(text).digest('hex')});
 }
 report.reading.levels.push({level:l,entries:40,minEojeol:Math.min(...counts),maxEojeol:Math.max(...counts),meanEojeol:+(counts.reduce((a,b)=>a+b)/40).toFixed(2),maxSentenceEojeol:Math.max(...lengths),uniqueSurfaceForms:vocab.size});
}
check(report.reading.items===600&&report.reading.questions===1800,'Reading counts');
const audio=JSON.parse(fs.readFileSync(path.join(root,'hangul-audio-audit.json'),'utf8'));
report.audio={...audio.counts,groups:{}};
for(const [label,group,total] of [['consonantNames','자음 이름',19],['vowels','모음',21],['syllables','글자판 음절',399]]){
 const items=audio.targets.filter(t=>t.groups.includes(group));
 report.audio.groups[label]={targets:items.length,filePresent:items.filter(t=>t.recordingAvailable).length,playbackAvailable:items.filter(t=>t.playbackAvailable).length,missing:items.filter(t=>!t.recordingAvailable).length,listeningApproved:0};check(items.length===total,'Audio alphabet count '+label);
}
report.warnings.push('Audio: missing human recordings and listening approval remain; no synthetic substitution.');
report.warnings.push('Exact supported-option uniqueness is an automated property, not a proof of every possible semantic interpretation.');
report.warnings.push('Level metrics describe this graded curriculum; no CEFR/TOPIK calibration or learner trial was performed.');
report.preservation.homepageUnchanged=fs.readFileSync(path.join(root,'index.html'),'utf8')===cp.execFileSync('git',['show',baseline+':index.html'],{cwd:root,encoding:'utf8'});check(report.preservation.homepageUnchanged,'Homepage modified');
fs.mkdirSync(path.join(root,'audit'),{recursive:true});fs.writeFileSync(path.join(root,'audit/phase2-content.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({lessons:report.lessons,reading:{...report.reading,entries:undefined},audio:report.audio,errors:report.errors,warnings:report.warnings},null,2));if(report.errors.length)process.exitCode=1;
