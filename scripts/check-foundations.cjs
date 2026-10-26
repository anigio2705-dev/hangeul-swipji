/* Run: node scripts/check-foundations.cjs */
'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const root=path.join(__dirname,'..'),read=name=>fs.readFileSync(path.join(root,name),'utf8');
function quiz(q){assert.equal(new Set(q[2]).size,q[2].length,'Duplicate choices');assert(Number.isInteger(q[3])&&q[3]>=0&&q[3]<q[2].length,'Invalid answer');}
(async()=>{
  const courses=['intro','beginner1','beginner2','intermediate1','intermediate2','advanced1','advanced2'];let total=0,questions=0;
  for(const name of courses){const html=read(name+'.html'),units=JSON.parse(html.match(/const units=(\[.*?\]);/s)[1]);assert.equal(units.length,50);for(const u of units){u.quiz.forEach(quiz);questions+=u.quiz.length;}total+=units.length;
    for(const match of html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>(.*?)<\/script>/gs))new vm.Script(match[1]);
    if(name==='intro'){assert.equal(units[14].sent[0][0],'외');assert.equal(units[19].sent[0][0],'바');assert.equal(units[0].v.length,10);assert.equal(units[1].v.length,14);assert.equal(new Set(units.map(x=>x.grammar[0][0])).size,50);for(let i=0;i<35;i++){if(i===4||i===3||i>=30)continue;for(const q of units[i].quiz)assert(!/뜻|mean|interpret/i.test(q[0]+' '+q[1]),'A letter sound is not a meaning.');}}
  }
  assert.equal(total,350);assert.equal(questions,1758);
  const context={window:{},document:{addEventListener(){},dispatchEvent(){}},Event:function(){},fetch:async()=>({ok:true,json:async()=>({recordings:{}})})};context.window.addEventListener=()=>{};vm.createContext(context);
  for(const file of ['hangul-core.js','hangul-week-data.js','hangul-week.js','hangul-board.js','active-recall.js'])new vm.Script(read(file));
  vm.runInContext(read('hangul-core.js'),context);await context.window.HSHangul.ready;vm.runInContext(read('hangul-week-data.js'),context);
  const H=context.window.HSHangul;assert.equal(H.consonants.length,19);assert.equal(H.vowels.length,21);const combinations=new Set();
  for(const [c] of H.consonants)for(const [v] of H.vowels){const block=H.compose(c,v),decomposed=block.normalize('NFD');assert.equal(decomposed.length,2);assert.equal((block.charCodeAt(0)-44032)%28,0);combinations.add(block);}assert.equal(combinations.size,399);assert.equal(H.compose('ㄱ','ㅏ'),'가');assert.equal(H.compose('ㄴ','ㅓ'),'너');assert.equal(H.compose('ㅂ','ㅏ'),'바');
  const days=context.window.HSWeek;assert.equal(days.length,7);let checks=0;for(const [i,d] of days.entries()){assert.equal(d.id,'H0'+(i+1));assert(d.steps.length>=4&&d.goal&&d.home&&d.ready);for(const q of d.quiz){quiz([q.prompt,q.en,q.choices,q.answer]);assert(q.why);checks++;}if(i===4)for(const [word]of d.practice)for(const ch of word)assert.equal((ch.charCodeAt(0)-44032)%28,0,'Keep first words free of finals.');}assert.equal(checks,40);
  const manifest=JSON.parse(read('hangul-audio-manifest.json'));for(const [word,a]of Object.entries(manifest.recordings)){assert(word&&a.author&&a.sourceUrl&&a.license&&a.licenseUrl&&a.review);const bytes=fs.readFileSync(path.join(root,a.src));assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'),a.sha256);assert(a.duration>.15&&a.duration<8);}
  console.log(`PASS: ${total} units / ${questions} course questions; 7 paired lessons / ${checks} new questions; ${combinations.size} blocks; ${Object.keys(manifest.recordings).length} attributed recordings.`);
})();
