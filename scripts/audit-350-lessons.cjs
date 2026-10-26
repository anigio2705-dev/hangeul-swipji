/* Phase 2: all 350 lessons content and curriculum quality gate.
   Run: node scripts/audit-350-lessons.cjs
   Generates phase2-lesson-audit.json without editing source lessons. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const courses=['intro','beginner1','beginner2','intermediate1','intermediate2','advanced1','advanced2'];
const report={version:1,scope:'source-structure-and-heuristic-review',generatedAt:new Date().toISOString(),courses:[],findings:[],summary:{units:0,questions:0,errors:0,warnings:0}};
const add=(severity,course,unit,message)=>{report.findings.push({severity,course,unit,message});report.summary[severity==='error'?'errors':'warnings']++};
for(const name of courses){
 const source=fs.readFileSync(path.join(root,name+'.html'),'utf8');
 const match=source.match(/const units=(\[.*?\]);/s);
 if(!match){add('error',name,0,'Cannot find embedded lesson data');continue}
 let units;try{units=JSON.parse(match[1])}catch(e){add('error',name,0,'Invalid embedded lesson JSON: '+e.message);continue}
 const row={course:name,units:units.length,questions:0,duplicateTitles:0,weakExplanations:0};
 if(units.length!==50)add('error',name,0,'Expected exactly 50 units');
 const titleSeen=new Map();
 units.forEach((u,i)=>{
  const n=i+1;report.summary.units++;
  const title=String(u.title||u.name||u.topic||'').trim();
  if(!title)add('warning',name,n,'No recognized title field');
  if(title){if(titleSeen.has(title)){row.duplicateTitles++;add('warning',name,n,'Repeated title from unit '+titleSeen.get(title))}else titleSeen.set(title,n)}
  if(!Array.isArray(u.quiz)||u.quiz.length===0){add('error',name,n,'No quiz questions');return}
  if(!Array.isArray(u.grammar)||!u.grammar.length){row.weakExplanations++;add('warning',name,n,'No grammar/explanation entries')}
  if(!Array.isArray(u.sent)||!u.sent.length)add('warning',name,n,'No sentence/example entries');
  const prompts=new Set();
  u.quiz.forEach((q,j)=>{
   row.questions++;report.summary.questions++;
   if(!Array.isArray(q)||q.length<4){add('error',name,n,'Malformed question '+(j+1));return}
   const [prompt,translation,choices,answer]=q;
   if(!String(prompt||'').trim())add('error',name,n,'Empty prompt Q'+(j+1));
   if(!Array.isArray(choices)||choices.length<2)add('error',name,n,'Missing choices Q'+(j+1));
   else if(new Set(choices.map(String)).size!==choices.length)add('error',name,n,'Duplicate choices Q'+(j+1));
   if(!Number.isInteger(answer)||!choices||answer<0||answer>=choices.length)add('error',name,n,'Invalid answer Q'+(j+1));
   const normalized=String(prompt||'').replace(/\s+/g,' ').trim();
   if(prompts.has(normalized))add('warning',name,n,'Repeated prompt Q'+(j+1));
   prompts.add(normalized);
  });
 });
 report.courses.push(row);
}
if(report.summary.units!==350)add('error','all',0,'Expected 350 lessons');
if(report.summary.questions!==1758)add('error','all',0,'Expected 1758 questions');
fs.writeFileSync(path.join(root,'phase2-lesson-audit.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({summary:report.summary,courses:report.courses,findings:report.findings.slice(0,20)},null,2));
if(report.summary.errors)process.exitCode=1;
