'use strict';
// Q007 only: no model calls, dispatcher, remote writes or deployment.
const fs=require('node:fs');
const path=require('node:path');
const http=require('node:http');
const crypto=require('node:crypto');
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const file=path.resolve(process.argv[2] || path.join(__dirname,'../intro.html'));
const source=fs.readFileSync(file,'utf8');
const raw=source.slice(source.indexOf('const units=')+12,source.indexOf(';\nconst ui='));
const units=JSON.parse(raw);
let checks=0;
function check(value,message){checks++;assert.ok(value,message);}
let server,browser;
(async()=>{
  server=http.createServer((req,res)=>{res.setHeader('Content-Type',req.url==='/intro.html'?'text/html; charset=utf-8':'application/javascript');res.end(req.url==='/intro.html'?source:'');});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  browser=await chromium.launch({headless:true,...(fs.existsSync('/usr/bin/chromium')?{executablePath:'/usr/bin/chromium'}:{})});
  const page=await browser.newPage();
  await page.route('**/*',route=>new URL(route.request().url()).hostname==='127.0.0.1'?route.continue():route.abort());
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`http://127.0.0.1:${server.address().port}/intro.html`);
  // Exercise the existing renderer first so the unmodified baseline fails in
  // the actual UI, rather than merely failing a new data-schema assertion.
  for(const language of ['ko','en']){
    for(let lesson=0;lesson<units.length;lesson++){
      const result=await page.evaluate(({language,lesson})=>{
        lang=language;unit=lesson;tab=3;selected={};state={done:{},mistakes:{},contentVersion:'20261026'};render();
        const host=document.getElementById('content');
        const buttons=()=>[...host.querySelectorAll('button')];
        const submit=()=>buttons().find(b=>b.textContent===ui[lang].submit);
        const selectAll=wrong=>[...host.querySelectorAll('.choices')].forEach((opts,i)=>opts.children[(units[unit].quiz[i][3]+(wrong?1:0))%units[unit].quiz[i][2].length].click());
        const clean=()=>JSON.stringify(state);
        const before=clean();submit().click();
        const unanswered={unchanged:clean()===before,message:host.querySelector('.feedback').textContent,expected:ui[lang].choose,explanations:host.querySelectorAll('.quiz-explanation').length};
        selectAll(false);submit().click();
        const expected=units[unit].quiz.map(q=>(lang==='ko'?'해설: ':'Explanation: ')+(q[4]||[])[lang==='ko'?0:1]);
        const correct={reasons:[...host.querySelectorAll('.quiz-explanation')].map(e=>e.textContent),score:host.querySelector('.feedback').textContent,expectedScore:ui[lang].result+': '+units[unit].quiz.length+' / '+units[unit].quiz.length,done:state.done[unit]===true,mistakes:Object.keys(state.mistakes).length,disabled:[...host.querySelectorAll('.choice')].every(b=>b.disabled),submitDisabled:submit().disabled};
        const stable=clean();submit().click();correct.resubmitUnchanged=clean()===stable;
        selected={};state={done:{},mistakes:{},contentVersion:'20261026'};render();selectAll(true);submit().click();
        const wrong={mistakes:Object.keys(state.mistakes).length,done:!!state.done[unit],reasons:host.querySelectorAll('.quiz-explanation').length,score:host.querySelector('.feedback').textContent,expectedScore:ui[lang].result+': 0 / '+units[unit].quiz.length};
        tab=4;selected={};render();selectAll(false);submit().click();
        const review={reasons:[...host.querySelectorAll('.quiz-explanation')].map(e=>e.textContent),mistakes:Object.keys(state.mistakes).length,done:!!state.done[unit]};
        const stored=JSON.parse(localStorage.getItem('hs-intro-v1'));
        const persist=JSON.stringify(stored)===JSON.stringify(state);
        selected={};render();
        return {unanswered,correct,wrong,review,expected,persist,afterRetry:host.querySelectorAll('.quiz-explanation').length};
      },{language,lesson});
      const count=units[lesson].quiz.length;
      check(result.unanswered.unchanged && result.unanswered.explanations===0 && result.unanswered.message===result.unanswered.expected,'unanswered must not reveal or save');
      check(result.correct.reasons.length===count,`lesson ${lesson+1} ${language}: expected ${count} rendered explanations, got ${result.correct.reasons.length}`);
      check(JSON.stringify(result.correct.reasons)===JSON.stringify(result.expected),'correct explanation text and language');
      check(result.correct.score===result.correct.expectedScore && result.correct.done && result.correct.mistakes===0,'correct score/done/mistakes');
      check(result.correct.disabled && result.correct.submitDisabled && result.correct.resubmitUnchanged,'disabled choices and duplicate-submit control');
      check(result.wrong.mistakes===count && !result.wrong.done && result.wrong.reasons===count && result.wrong.score===result.wrong.expectedScore,'wrong score and persistence');
      check(JSON.stringify(result.review.reasons)===JSON.stringify(result.expected),'review must show same bilingual reasons');
      check(result.review.mistakes===0 && !result.review.done && result.persist && result.afterRetry===0,'review clears only mistakes; retry clears results');
    }
  }
  check(errors.length===0,'no browser exceptions: '+errors.join(';'));
  check(units.length===50 && units.reduce((n,u)=>n+u.quiz.length,0)===258,'all 50 units /258 questions');
  for(const u of units)for(const q of u.quiz){
    check(q.length===5 && q[4].length===2 && q[4].every(x=>typeof x==='string'&&x.length>20),'bilingual nonempty authored explanation');
    check(new Set(q[2]).size===q[2].length && Number.isInteger(q[3]) && q[3]>=0 && q[3]<q[2].length,'unique options and valid answer');
  }
  const original=units.map(u=>({...u,quiz:u.quiz.map(q=>q.slice(0,4))}));
  const originalHash=crypto.createHash('sha256').update(JSON.stringify(original)).digest('hex');
  check(originalHash==='4dbe645c7af209f682c3c075a38a5daab6d134a77b753c3e57c1ec1a0b660c00','all original lessons, prompts, choices, keys and order preserved');
  // textContent must display text without creating executable markup.
  const injection=await page.evaluate(()=>{
    unit=0;lang='en';tab=3;selected={};const q=units[0].quiz[0],old=q[4][1];
    q[4][1]='<img src=x onerror="window.__q007Injected=true">';render();
    const host=document.getElementById('content');[...host.querySelectorAll('.choices')].forEach((opts,i)=>opts.children[units[0].quiz[i][3]].click());
    [...host.querySelectorAll('button')].find(b=>b.textContent===ui.en.submit).click();
    const safe=!host.querySelector('.quiz-explanation img')&&!window.__q007Injected&&host.querySelector('.quiz-explanation').textContent.includes('<img');q[4][1]=old;return safe;
  });
  check(injection,'explanations must be rendered as inert text');
  await page.setViewportSize({width:390,height:844});
  check(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'mobile content fits viewport');
  console.log(JSON.stringify({task:'Q007',units:50,questions:258,languages:2,browser_scenarios:300,checks,result:'PASS',server_calls:0,product_deployed:false}));
})().catch(error=>{console.error(error.stack);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();if(server)await new Promise(resolve=>server.close(resolve));});
