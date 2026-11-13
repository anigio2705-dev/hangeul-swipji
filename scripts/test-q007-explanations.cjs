'use strict';
// Execute the actual quiz/review functions in a deterministic DOM simulation.
// This does not claim a real browser, layout, media, teacher or server B review.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const assert=require('node:assert/strict'),crypto=require('node:crypto');
const source=fs.readFileSync(path.resolve(process.argv[2]||path.join(__dirname,'../intro.html')),'utf8');
const unitsText=source.slice(source.indexOf('const units=')+12,source.indexOf(';\nconst ui='));
const units=JSON.parse(unitsText);
class Element{
  constructor(tag){this.tagName=tag;this.children=[];this.attributes={};this.style={};this.disabled=false;this._text='';}
  set textContent(v){this._text=String(v);this.children=[];}
  get textContent(){return this._text+this.children.map(x=>typeof x==='string'?x:x.textContent).join('');}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this._text='';this.children=[...nodes];}
  setAttribute(k,v){this.attributes[k]=v;}
  getAttribute(k){return this.attributes[k];}
  querySelectorAll(selector){
    const found=[];const matches=e=>selector.startsWith('.')?e.className?.split(' ').includes(selector.slice(1)):e.tagName===selector;
    for(const x of this.children)if(x instanceof Element){if(matches(x))found.push(x);found.push(...x.querySelectorAll(selector));}
    return found;
  }
  click(){if(!this.disabled&&this.onclick)this.onclick();}
}
const elements={};for(const id of ['content','nav','progressLabel','progressBar'])elements[id]=new Element('div');
for(let i=0;i<50;i++)elements.nav.append(new Element('button'));
const storage=new Map();
const context=vm.createContext({document:{createElement:tag=>new Element(tag),getElementById:id=>elements[id]},
 localStorage:{setItem:(k,v)=>storage.set(k,v),getItem:k=>storage.get(k)},window:{location:{}},console});
const uiText=source.slice(source.indexOf('const ui='),source.indexOf('let lang='));
const functions=source.slice(source.indexOf('function renderQuiz('),source.indexOf('$("filterLessons").addEventListener'));
const button=source.slice(source.indexOf('function button('),source.indexOf('const authoredManuscripts='));
vm.runInContext('const units='+unitsText+';'+uiText+`
 let lang='ko',unit=0,tab=3,selected={},state={done:{},mistakes:{}};
 const key=(u,q)=>u+'-'+q;
 const save=()=>localStorage.setItem('hs-intro-v1',JSON.stringify(state));
 function render(){if(tab===4)renderReview($('content'));else renderQuiz($('content'),units[unit].quiz.map((q,i)=>({u:unit,i,q})),false);}
 `+button+functions,context,{timeout:2000});
let checks=0;
function check(v,message){checks++;assert.ok(v,message);}
function evaluate(s){return vm.runInContext(s,context,{timeout:2000});}
function buttons(){return elements.content.querySelectorAll('button');}
function submit(){return buttons().find(b=>b.textContent===evaluate('ui[lang].submit'));}
function reasons(){return elements.content.querySelectorAll('.quiz-explanation').map(e=>e.textContent);}
function select(lesson,wrong){elements.content.querySelectorAll('.choices').forEach((opts,i)=>opts.children[(units[lesson].quiz[i][3]+(wrong?1:0))%units[lesson].quiz[i][2].length].click());}
for(const language of ['ko','en'])for(let lesson=0;lesson<units.length;lesson++){
 evaluate(`lang=${JSON.stringify(language)};unit=${lesson};tab=3;selected={};state={done:{},mistakes:{}};render();`);
 const before=evaluate('JSON.stringify(state)');submit().click();
 check(evaluate('JSON.stringify(state)')===before && reasons().length===0,'unanswered must not save/reveal');
 check(elements.content.querySelectorAll('.feedback')[0].textContent===evaluate('ui[lang].choose'),'unanswered guidance');
 select(lesson,false);submit().click();
 const count=units[lesson].quiz.length;
 check(reasons().length===count,`lesson ${lesson+1} ${language}: expected ${count} rendered explanations, got ${reasons().length}`);
 const expected=units[lesson].quiz.map(q=>(language==='ko'?'해설: ':'Explanation: ')+q[4][language==='ko'?0:1]);
 check(JSON.stringify(reasons())===JSON.stringify(expected),'correct language/text');
 check(evaluate('state.done[unit]===true && Object.keys(state.mistakes).length===0'),'correct updates completion');
 check(elements.content.querySelectorAll('.feedback')[0].textContent===evaluate('ui[lang].result')+': '+count+' / '+count,'correct score');
 check(submit().disabled && elements.content.querySelectorAll('.choice').every(b=>b.disabled),'submitted controls disabled');
 const saved=evaluate('JSON.stringify(state)');submit().click();check(evaluate('JSON.stringify(state)')===saved,'duplicate submit no change');
 buttons().find(b=>b.textContent===evaluate('ui[lang].retry')).click();
 check(reasons().length===0 && evaluate('Object.keys(selected).length===0'),'retry resets selection/results');
 evaluate('state={done:{},mistakes:{}};render();');select(lesson,true);submit().click();
 check(evaluate('Object.keys(state.mistakes).length')===count && !evaluate('state.done[unit]'),'wrong answers saved; not complete');
 check(elements.content.querySelectorAll('.feedback')[0].textContent===evaluate('ui[lang].result')+': 0 / '+count && reasons().length===count,'wrong score/reasons');
 evaluate('tab=4;selected={};render();');select(lesson,false);submit().click();
 check(JSON.stringify(reasons())===JSON.stringify(expected),'review explanation matches');
 check(evaluate('Object.keys(state.mistakes).length===0 && !state.done[unit]'),'review removes mistakes without marking lesson complete');
 check(storage.get('hs-intro-v1')===evaluate('JSON.stringify(state)'),'state persisted');
 evaluate('selected={};render();');check(reasons().length===0 && elements.content.querySelectorAll('.choices').length===0,'empty review clears results');
}
check(units.length===50 && units.reduce((n,u)=>n+u.quiz.length,0)===258,'all lessons/questions');
for(const u of units)for(const q of u.quiz){
 check(q.length===5 && q[4].length===2 && q[4].every(x=>typeof x==='string'&&x.length>20),'two nonempty explanations');
 check(new Set(q[2]).size===q[2].length && Number.isInteger(q[3]) && q[3]>=0 && q[3]<q[2].length,'unique options and valid answer');
}
const original=units.map(u=>({...u,quiz:u.quiz.map(q=>q.slice(0,4))}));
check(crypto.createHash('sha256').update(JSON.stringify(original)).digest('hex')==='4dbe645c7af209f682c3c075a38a5daab6d134a77b753c3e57c1ec1a0b660c00','all original content and keys preserved');
evaluate(`unit=0;lang='en';tab=3;selected={};units[0].quiz[0][4][1]='<img src=x onerror="alert(1)">';render();`);
select(0,false);submit().click();
check(reasons()[0]==='Explanation: <img src=x onerror="alert(1)">' && !elements.content.querySelectorAll('img').length,'inert text rendering');
console.log(JSON.stringify({task:'Q007',runtime:'Node + DOM simulation',units:50,questions:258,languages:2,quiz_flows:300,checks,result:'PASS',real_browser_verified:false,server_model_calls:0,product_deployed:false}));
