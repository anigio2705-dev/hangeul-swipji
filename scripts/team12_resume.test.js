'use strict';
const assert=require('node:assert/strict');
const {nextLesson,lessonFromQuery}=require('./team12_resume.js');
assert.equal(nextLesson({}),1);
assert.equal(nextLesson({done:{0:true,1:true,2:false}}),3);
assert.equal(nextLesson({done:{0:'true'}}),1,'string is not completion');
assert.equal(nextLesson({done:{0:1}}),1,'numeric flag is not completion');
assert.equal(nextLesson({done:Object.fromEntries(Array.from({length:50},(_,i)=>[i,true]))}),50);
assert.equal(nextLesson({done:{0:true,1:true}},3),3);
assert.equal(lessonFromQuery('?unit=1'),1);
assert.equal(lessonFromQuery('?unit=50'),50);
for(const q of ['?unit=0','?unit=51','?unit=-1','?unit=2.5','?unit=abc','?unit=9999999999999999999'])assert.equal(lessonFromQuery(q),null,q);
assert.equal(lessonFromQuery('?review=1'),null);
console.log('team12 resume tests passed');

const html=require('node:fs').readFileSync(require('node:path').join(__dirname,'..','dashboard.html'),'utf8');
const helper=html.indexOf('<script src="./scripts/team12_resume.js"></script>');
const inline=html.indexOf('<script>');
assert.ok(helper>=0&&inline>=0&&helper<inline,'resume helper must load before inline dashboard render');
