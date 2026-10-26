/* Phase-one automated beginner lesson simulation (not a real human pilot).
   Run: node scripts/check-week-learning-simulation.cjs */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.join(__dirname,'..'),read=p=>fs.readFileSync(path.join(root,p),'utf8');
const sandbox={window:{}};vm.createContext(sandbox);vm.runInContext(read('hangul-week-data.js'),sandbox);
const days=sandbox.window.HSWeek;
assert.equal(days.length,7);
const results=[];
for(const [dayIndex,d] of days.entries()){
 assert.equal(d.id,'H0'+(dayIndex+1));
 assert.equal(d.steps.length,4);
 assert(d.goal&&d.goalEn&&d.instruction&&d.home&&d.ready);
 assert(d.write.length>0&&d.practice.length>0);
 const questions=d.quiz;
 const seen=new Set();
 for(const [i,q] of questions.entries()){
  assert.equal(q.choices.length,4,`${d.id} Q${i+1}: four choices required`);
  assert.equal(new Set(q.choices).size,4,`${d.id} Q${i+1}: duplicate choices`);
  assert(Number.isInteger(q.answer)&&q.answer>=0&&q.answer<4);
  assert(q.prompt&&q.en&&q.why);
  assert(!seen.has(q.prompt),`${d.id}: duplicate question`);seen.add(q.prompt);
 }
 const correct=questions.map(q=>q.answer);
 const wrong=questions.map(q=>(q.answer+1)%4);
 const score=answers=>questions.reduce((n,q,i)=>n+(answers[i]===q.answer),0);
 const pass=score(correct)>=Math.ceil(questions.length*.8);
 assert.equal(score(correct),questions.length);
 assert.equal(score(wrong),0);
 assert(pass);
 assert(score(wrong)<Math.ceil(questions.length*.8));
 // A mixed answer set just below the pass threshold must not be marked passed.
 const near=correct.map((a,i)=>i<Math.ceil(questions.length*.8)-1?a:(a+1)%4);
 assert(score(near)<Math.ceil(questions.length*.8));
 results.push({day:d.id,title:d.title,questions:questions.length,perfect:score(correct),wrong:score(wrong),passThreshold:Math.ceil(questions.length*.8),teacherSteps:d.steps.length,practice:d.practice.length});
}
assert.equal(results.reduce((n,r)=>n+r.questions,0),40);
const html=read('hangul-week.html'),app=read('hangul-week.js');
assert(html.includes('data-audio-status'),'Audio status needed');
assert(html.includes('교사용')&&html.includes('학생용'),'Paired editions needed');
assert(app.includes('localStorage.setItem'),'Progress storage needed');
assert(app.includes('H.soundButton'),'Sound controls needed');
const report={kind:'automated-learning-simulation',humanLearners:0,humanTeacherListeningApprovals:0,days:7,questions:40,results,conclusion:'Code and answer-key consistency checks only. No pronunciation, usability, or human learning outcomes validated.'};
console.log(JSON.stringify(report,null,2));
