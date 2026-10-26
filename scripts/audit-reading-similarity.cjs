/* Similarity diagnostics are heuristics, not human semantic or level certification. */
'use strict';
const fs=require('node:fs'),vm=require('node:vm'),cp=require('node:child_process'),assert=require('node:assert/strict');
const {root,reading}=require('./curriculum-source.cjs');
const baseline='3eaec8576d15866a2a78051c082cdee9093281ba';
const old=file=>cp.execFileSync('git',['show',baseline+':'+file],{cwd:root,encoding:'utf8'});
const ctx={document:{getElementById(){return {}}},localStorage:{getItem(){return null}},window:{}};vm.createContext(ctx);
vm.runInContext(old('reading-curriculum.js')+'\n'+old('reading.html').match(/<script>\s*([\s\S]*?)<\/script>/)[1].split('function icon(')[0]+';globalThis.get=content',ctx);
const now=reading(),grams=x=>{const words=x.join(' ').split(/\s+/);return new Set(words.slice(2).map((_,i)=>words.slice(i,i+3).join(' ')))};
const jac=(a,b)=>{const union=new Set([...a,...b]);return union.size?[...a].filter(v=>b.has(v)).length/union.size:0};
function metrics(get){const levels=[];let near=0,progressivePrefixes=0;for(let l=1;l<=15;l++){
 const all=Array.from({length:40},(_,i)=>get(l,i+1)),pair=all.slice(0,20).map((x,i)=>({family:i+1,sentenceJaccard:jac(new Set(x.paragraphs),new Set(all[i+20].paragraphs)),eojeolTrigramJaccard:jac(grams(x.paragraphs),grams(all[i+20].paragraphs))}));
 let similar=0,max=0;for(let a=0;a<40;a++)for(let b=a+1;b<40;b++){const score=jac(grams(all[a].paragraphs),grams(all[b].paragraphs));max=Math.max(max,score);if(score>=.65)similar++}near+=similar;
 if(l<15)for(let b=1;b<=40;b++){const next=get(l+1,b);if(all[b-1].paragraphs.every((p,i)=>p===next.paragraphs[i]))progressivePrefixes++}
 levels.push({level:l,nearPairsAtTrigramThreshold065:similar,maxTrigramJaccard:+max.toFixed(4),pairedStories:pair});
}return {levels,totalNearPairs:near,progressivePrefixes}};
const before=metrics(ctx.get),after=metrics(now.get);assert(after.totalNearPairs<before.totalNearPairs,'No similarity reduction');
let inferenceQuestions=0;for(let l=1;l<=15;l++)for(let b=1;b<=40;b++)inferenceQuestions+=now.get(l,b).q.filter(q=>q.type==='inference').length;
assert.equal(inferenceQuestions,60);
const grammarPatterns={conditional:/(?:으면|다면|면\s)/,contrast:/(?:지만|그러나|하지만)/,reportedSpeech:/(?:다고|냐고|라고)/,embeddedQuestion:/(?:는지|인지|했는지)/,concession:/(?:더라도|아도|어도)/,evidenceAndLimits:/(?:근거|기준|범위|보장|구분)/};
const grammarProfiles=Array.from({length:15},(_,i)=>({level:i+1,features:Object.fromEntries(Object.entries(grammarPatterns).map(([label,re])=>[label,Array.from({length:40},(_,b)=>now.get(i+1,b+1).paragraphs.join(' ')).filter(t=>re.test(t)).length]))}));
const report={baseline,grammarProfiles,grammarProfileLimit:'Surface-form heuristics with possible false matches; no grammar mastery certification',scope:'All 600 current entries; all 11700 same-level pairs; 560 neighboring-level comparisons',method:'Jaccard of exact Korean sentences and space-delimited eojeol trigrams; threshold .65 is diagnostic, not semantic proof',before,after,inferenceQuestions,aiEditorialReview:{distinctAlternateStories:20,newBilingualSentencePairs:280,inferenceTemplates:10,reusedAtLevels:[10,11,12,13,14,15],review:'Checked chronology, Korean/English sentence alignment, explicit evidence and contradiction/overstatement in inference distractors. Literal option checks cannot prove semantic uniqueness; these ten templates were separately read against their full context.'},limitations:['All 40 stories intentionally grow through adjacent levels: prefix repetition remains.','600 entries are graded variants of 40 story families, not 600 independent stories.','Difficulty metrics do not establish CEFR/TOPIK calibration or beginner learning effectiveness.','No teacher approval or learner trial.']};
fs.writeFileSync(root+'/audit/reading-similarity.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({before:before.totalNearPairs,after:after.totalNearPairs,prefixes:after.progressivePrefixes,inferenceQuestions}));
