/* Phase 2 static responsive, lesson and persistence smoke checks.
   Does not replace real browser/device testing. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),read=f=>fs.readFileSync(path.join(root,f),'utf8');
const pages=['index.html','learn.html','intro.html','beginner1.html','beginner2.html','intermediate1.html','intermediate2.html','advanced1.html','advanced2.html','hangul-basics.html','hangul-week.html','reading.html'];
let count=0;
for(const file of pages){
 const html=read(file);
 assert(/<meta\s+name=["']viewport["']/i.test(html),file+': missing viewport meta');
 assert(/<html/i.test(html)&&/<\/html>/i.test(html),file+': invalid HTML shell');
 assert(/<title[^>]*>[^<]+<\/title>/i.test(html),file+': missing page title');
 assert(!/href=["']#["']/.test(html),file+': placeholder link found');
 count++;
}
for(const file of ['intro.html','beginner1.html','beginner2.html','intermediate1.html','intermediate2.html','advanced1.html','advanced2.html']){
 const html=read(file);assert(/const units=\[/.test(html),file+': missing course data');
}
assert(read('hangul-week.js').includes('localStorage.setItem'),'Seven-day progress save missing');
assert(read('hangul-core.js').includes('audio'),'Audio player code missing');
console.log('PASS: '+count+' pages passed source-level responsive shell checks. Real PC/mobile device testing is still required.');
