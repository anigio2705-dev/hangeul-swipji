'use strict';
// Task #42: independent semantic contract for seven free course entry routes.
// Static/Node checks only; browser and actual learner comprehension remain separate.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(root,'learn.html'),'utf8');
const scripts=[...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)];
const source=scripts.map(m=>m[1]).find(s=>s.includes('const courses='));
assert.ok(source,'Main course script missing');
new vm.Script(source,{filename:'learn.html#main'});
function extract(name){
 const m=source.match(new RegExp('const '+name+'=(\\[[\\s\\S]*?\\]);'));
 assert.ok(m,name+' data missing');return vm.runInNewContext(m[1]);
}
const courses=extract('courses'),prereqs=extract('suggestedFirst');
const expected=['intro.html','beginner1.html','beginner2.html','intermediate1.html','intermediate2.html','advanced1.html','advanced2.html'];
function audit(cs,ps){
 assert.equal(cs.length,7);assert.equal(ps.length,7);
 assert.deepEqual(Array.from(cs,c=>c[2]),expected,'Stable seven-course routes');
 for(let i=0;i<7;i++){
  assert.equal(cs[i].length,5);assert.ok(cs[i][0]&&cs[i][1]&&cs[i][3]&&cs[i][4]);
  assert.ok(fs.existsSync(path.join(root,cs[i][2])),'Broken course link '+cs[i][2]);
  assert.equal(ps[i].length,2);
  if(i===0){assert.ok(ps[i][0].includes('선행 없음'));assert.ok(ps[i][1].includes('No prerequisite'))}
  else{assert.ok(ps[i][0].includes(cs[i-1][0]),'Incorrect Korean prerequisite');
       assert.ok(ps[i][1].includes(cs[i-1][1]),'Incorrect English prerequisite')}
 }
}
audit(courses,prereqs);
assert.ok(html.includes('<small class="prereq"></small>'),'Prerequisite label missing');
assert.ok(source.includes('a.querySelector(".prereq").textContent=suggestedFirst[i][en?1:0]'),'Prerequisite rendering missing');
assert.ok(source.includes('a.href="./"+c[2]'),'Courses must remain directly accessible');
const bad=prereqs.map(x=>[...x]);bad[3][1]='Suggested first: Beginner 1';
assert.throws(()=>audit(courses,bad),/Incorrect English prerequisite/);
const badRoutes=courses.map(x=>[...x]);badRoutes[6][2]='missing-course.html';
assert.throws(()=>audit(badRoutes,prereqs),/Stable seven-course routes/);
console.log('PASS #42 seven course routes, bilingual suggested prerequisites, direct entry, negative fixtures');
