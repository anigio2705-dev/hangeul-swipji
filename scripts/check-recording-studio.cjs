'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.join(__dirname,'..');
const {build}=require('./team12_recording_queue.js');
const manifest=JSON.parse(fs.readFileSync(path.join(root,'hangul-audio-manifest.json'),'utf8'));
const q=build(manifest);
assert.equal(q.entries.length,399);
assert.deepEqual(q.counts,{missing:354,held:26,ready_unapproved:19});
assert.deepEqual(q.missing.slice(0,12).map(x=>x.character),['고','노','누','도','라','마','바','자','카','타','파','하']);
assert.equal(q.entries.find(x=>x.character==='가').status,'ready_unapproved');
assert.equal(q.entries.find(x=>x.character==='개').status,'held');
assert.equal(q.missing.find(x=>x.character==='고').filename,'hangul-human-ace0.webm');
assert.throws(()=>build(null),TypeError);
const html=fs.readFileSync(path.join(root,'hangul-recording-studio.html'),'utf8');
for(const marker of ['getUserMedia','MediaRecorder','URL.revokeObjectURL','getTracks()','consent','review','download','local only'])
 assert(html.includes(marker),'Missing safe studio control '+marker);
assert(fs.readFileSync(path.join(root,'hangul-audio-review.html'),'utf8').includes('href="./hangul-recording-studio.html"'));
assert(!/fetch\s*\([^)]*method\s*:\s*['"]POST/.test(html),'Studio must not upload audio');
console.log('PASS: 399 syllables, priority missing queue, consent-gated local recorder and review controls');
