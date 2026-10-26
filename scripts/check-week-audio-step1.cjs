/* File acquisition check only. This does not approve pronunciation. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict'),vm=require('node:vm');
const root=path.join(__dirname,'..'),read=n=>fs.readFileSync(path.join(root,n),'utf8');
const report=JSON.parse(read('hangul-week-audio-step1.json')),m=JSON.parse(read('hangul-audio-manifest.json'));
assert.equal(report.prepared,52);assert.equal(report.items.length,52);assert.equal(new Set(report.items.map(x=>x.text)).size,52);assert.equal(new Set(report.items.map(x=>x.sha256)).size,52);
let human=0,synthetic=0;
for(const x of report.items){const a=x.kind==='synthetic'?(m.retiredSynthetic||{})[x.text]:m.recordings[x.text];assert(a&&a.stage1Candidate&&a.disabled);assert.equal(a.src,x.src);assert.equal(a.sha256,x.sha256);assert(a.author&&a.license&&a.licenseUrl&&a.sourceUrl);assert(a.duration>.2&&a.duration<8);assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(root,a.src))).digest('hex'),a.sha256);if(a.kind==='human'){human++;assert(a.sourceUrl.startsWith('https://commons.wikimedia.org/'));}else{synthetic++;assert.equal(a.kind,'synthetic');assert.equal(a.inputText,x.text+'.');assert.equal(a.language,'ko');assert(a.generationText.includes(x.text)&&a.modelRevision);assert.equal(a.segment.repetitions,2);}}
assert.equal(human,report.newHuman);assert.equal(synthetic,report.newSynthetic);
const c={window:{}};vm.createContext(c);vm.runInContext(read('hangul-week-data.js'),c);const targets=new Set(c.window.HSWeek.flatMap(d=>d.practice.map(([word,name])=>d.id==='H01'?name:word)));
assert.equal(targets.size,63);for(const t of targets)assert(m.recordings[t]||(m.retiredSynthetic||{})[t],'Missing historical '+t);assert.equal(report.listeningApproved,0);assert.equal(report.publicPlaybackOfNewCandidates,false);
console.log(`PASS: 52/52 new candidate files (${human} human, ${synthetic} synthetic), historical 63/63 coverage. Current human-only policy excludes archived synthetic files.`);
