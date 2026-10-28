/* 7-day human-audio coverage gate. Run: node scripts/check-week-human-audio.cjs */
'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const manifest=JSON.parse(read('hangul-audio-manifest.json'));
const context={window:{}};vm.createContext(context);vm.runInContext(read('hangul-week-data.js'),context);
const lessons=context.window.HSWeek;assert.equal(lessons.length,7);
const targets=[...new Set(lessons.flatMap(d=>d.practice.map(([word,label])=>d.id==='H01'?label:word)))];
assert.equal(targets.length,63,'7-day target set changed; review curriculum before updating expectations');
const missing=[],held=[],ready=[],invalid=[];const sourceOwners=new Map();
for(const word of targets){
 const r=manifest.recordings[word];
 if(!r){missing.push(word);continue;}
 if(r.kind!=='human'){invalid.push(word);continue;}
 if(typeof r.src!=='string'||!/^\.\/assets\/hangul-audio\/[\w-]+\.mp3$/.test(r.src)||!(/^[a-f0-9]{64}$/i.test(r.sha256||''))||!r.sourceUrl||!r.author||!r.license){invalid.push(word);continue;}
 const file=path.resolve(root,r.src);
 if(!file.startsWith(root+path.sep)||!fs.existsSync(file)){invalid.push(word);continue;}
 if(sourceOwners.has(r.src)){invalid.push(word);continue;}
 sourceOwners.set(r.src,word);
 if(r.disabled||r.stage1Candidate){held.push(word);}else{ready.push(word);}
}
const result={targetCount:targets.length,humanCandidateCount:ready.length+held.length,missingCount:missing.length,missing,heldCount:held.length,readyForPlaybackCount:ready.length,invalid,teacherListeningApproved:false,notes:'File presence is not pronunciation approval. Held candidates require human listening review.'};
console.log(JSON.stringify(result,null,2));
if(invalid.length)process.exitCode=1;
