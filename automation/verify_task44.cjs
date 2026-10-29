'use strict';
// #44: Execute the actual seven course-page scripts in a minimal DOM harness.
// This is a deterministic simulated DOM regression, not real-browser approval.
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const courses=['intro','beginner1','beginner2','intermediate1','intermediate2','advanced1','advanced2'];
class Element {
  constructor(tag='div'){
    this.tagName=tag;this.children=[];this.attributes={};this.dataset={};
    this.textContent='';this.value='';this.className='';this.style={};this.hidden=false;this.disabled=false;
    this.listeners={};
  }
  append(...nodes){this.children.push(...nodes);}
  appendChild(node){this.children.push(node);return node;}
  replaceChildren(...nodes){this.children=nodes;}
  setAttribute(k,v){this.attributes[k]=v;}
  addEventListener(k,fn){this.listeners[k]=fn;}
  scrollIntoView(){}
  querySelectorAll(selector){
    const out=[];
    const visit=node=>{
      for(const child of node.children){
        if(selector==='.choice'&&child.className.split(' ').includes('choice'))out.push(child);
        if(selector==='button'&&child.tagName==='button')out.push(child);
        if(child&&child.children)visit(child);
      }
    };
    visit(this);return out;
  }
}
function load(course,storage){
  const html=fs.readFileSync(path.join(root,course+'.html'),'utf8');
  const blocks=[...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)];
  const main=blocks.find(block=>block[1].includes('const units='));
  assert.ok(main,course+': missing inline course script');
  const ids=new Map(),get=id=>{if(!ids.has(id))ids.set(id,new Element());return ids.get(id)};
  const document={
    documentElement:{lang:'ko'},getElementById:get,createElement:tag=>new Element(tag),
    addEventListener(){},querySelectorAll(){return []}
  };
  const localStorage={
    getItem:key=>storage.has(key)?storage.get(key):null,
    setItem:(key,value)=>storage.set(key,String(value))
  };
  const window={matchMedia:()=>({matches:false}),addEventListener(){},location:{href:''}};
  const sandbox=vm.createContext({document,window,localStorage,
    location:{search:'',pathname:'/'+course+'.html'},URLSearchParams,console,
    alert(){throw Error('Unexpected alert')},
    speechSynthesis:{cancel(){},speak(){throw Error('No audio in test')}},
    SpeechSynthesisUtterance:class{},setTimeout,clearTimeout
  });
  vm.runInContext(main[1],sandbox,{filename:course+'.html#main',timeout:7000});
  return {get,sandbox,storage,units:vm.runInContext('units',sandbox),
    ui:vm.runInContext('ui',sandbox)};
}
function chooseAndSubmit(view,answers,unitIndex=0){
  const {get,units,ui}=view,content=get('content'),q=units[unitIndex].quiz;
  const sections=content.children.filter(x=>x.className==='mistake');
  assert.equal(sections.length,q.length,'Quiz question count');
  sections.forEach((section,i)=>{
    const opts=section.children.find(x=>x.className==='choices');
    assert.ok(opts,'Missing options');
    assert.equal(opts.children.length,q[i][2].length,'Answer count');
    opts.children[answers[i]].onclick();
  });
  const submit=content.children.find(x=>x.tagName==='button'&&x.textContent===ui.ko.submit);
  assert.ok(submit,'Missing submit control');submit.onclick();
}
for(const course of courses){
  const store=new Map(),view=load(course,store),{get,units}=view;
  assert.equal(units.length,50,course+': expected 50 lessons');
  assert.equal(get('nav').children.length,50,course+': lesson list');
  assert.equal(get('tabs').children.length,5,course+': lesson tabs');
  assert.ok(get('lessonTitle').textContent,'Missing lesson title');
  assert.ok(get('coachPhrase').textContent,'Missing lesson example');
  get('tabs').children[3].onclick();
  const q=units[0].quiz;
  assert.ok(q.length>=1,course+': missing exercises');
  const wrong=q.map(x=>(x[3]+1)%x[2].length);
  chooseAndSubmit(view,wrong);
  // #45 partial-score and retry regression against the real course script.
  const firstFeedback=get('content').children.find(x=>x.className==='feedback');
  assert.ok(firstFeedback,course+': score feedback missing');
  assert.equal(firstFeedback.textContent,view.ui.ko.result+': 0 / '+q.length,
    course+': all-wrong score miscalculated');
  const retryRow=get('content').children.find(x=>x.className==='row');
  assert.ok(retryRow,course+': retry controls missing');
  const retryButton=retryRow.children.find(x=>x.tagName==='button'&&x.textContent===view.ui.ko.retry);
  assert.ok(retryButton,course+': retry button missing');
  retryButton.onclick();
  assert.equal(get('content').children.filter(x=>x.className==='mistake').length,q.length,
    course+': retry did not restore quiz');
  // #45 bounded partial-score regression: one correct + all other answers wrong.
  // A retry must re-score from the new selections, never carry old points.
  assert.ok(q.length>=2,course+': partial score requires two questions');
  const mixed=q.map((x,i)=>i===0?x[3]:(x[3]+1)%x[2].length);
  chooseAndSubmit(view,mixed);
  const partialFeedback=get('content').children.find(x=>x.className==='feedback');
  assert.equal(partialFeedback?.textContent,view.ui.ko.result+': 1 / '+q.length,
    course+': mixed score miscalculated');
  const key='hs-'+course+'-v1';
  let mixedSaved=JSON.parse(store.get(key));
  assert.equal(Object.keys(mixedSaved.mistakes).length,q.length-1,
    course+': partial quiz wrong-answer count');
  assert.ok(!mixedSaved.done['0'],course+': partial score incorrectly marked complete');
  function retryCurrent(){
    const row=get('content').children.find(x=>x.className==='row');
    const button=row?.children.find(x=>x.tagName==='button'&&x.textContent===view.ui.ko.retry);
    assert.ok(button,course+': retry control disappeared');button.onclick();
  }
  retryCurrent();
  chooseAndSubmit(view,wrong);
  retryCurrent();
  let saved=JSON.parse(store.get(key));
  assert.equal(Object.keys(saved.mistakes).length,q.length,course+': wrong answers not saved');
  assert.ok(!saved.done['0'],course+': wrong answers marked complete');
  get('tabs').children[4].onclick();
  assert.equal(get('content').children.filter(x=>x.className==='mistake').length,q.length,
    course+': wrong-answer review missing');
  chooseAndSubmit(view,q.map(x=>x[3]));
  saved=JSON.parse(store.get(key));
  assert.equal(Object.keys(saved.mistakes).length,0,course+': corrected answers not cleared');
  get('tabs').children[3].onclick();
  chooseAndSubmit(view,q.map(x=>x[3]));
  saved=JSON.parse(store.get(key));
  assert.equal(saved.done['0'],true,course+': full score did not persist completion');
  const row=get('content').children.find(x=>x.className==='row');
  assert.ok(row,course+': missing post-quiz navigation');
  const next=row.children.find(x=>x.tagName==='button'&&x.textContent===view.ui.ko.next);
  assert.ok(next,course+': next unit button missing');
  next.onclick();
  assert.equal(get('lessonTitle').textContent,units[1].title[0],course+': next unit not selected');
  const resumed=load(course,store);
  assert.ok(resumed.get('nav').children[0].textContent.startsWith('✓ '),
    course+': completion not restored on reload');
  // Exercise every remaining unit's actual quiz and persisted completion, not
  // just the first representative lesson. This is still a DOM simulation.
  for(let i=1;i<50;i++){
    resumed.get('nav').children[i].onclick();
    resumed.get('tabs').children[3].onclick();
    const questions=units[i].quiz;
    assert.ok(questions.length>0,course+': missing unit '+(i+1)+' quiz');
    questions.forEach(q=>assert.ok(Number.isInteger(q[3])&&q[3]>=0&&q[3]<q[2].length,
      course+': invalid correct answer index in unit '+(i+1)));
    chooseAndSubmit(resumed,questions.map(q=>q[3]),i);
  }
  const finished=JSON.parse(store.get(key));
  assert.equal(Object.values(finished.done).filter(Boolean).length,50,
    course+': all 50 units must persist successful completion');
  const finalReload=load(course,store);
  assert.equal(finalReload.get('nav').children.filter(n=>n.textContent.startsWith('✓ ')).length,50,
    course+': all completed lessons must survive reload');
  console.log('PASS #44 '+course+': 50 unit quizzes, wrong answer, review, full score, next, reload');
}
console.log('PASS #44 seven courses: 350 lessons simulated in actual course scripts');
