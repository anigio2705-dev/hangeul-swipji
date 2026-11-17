/* Local browser checks. Google translation itself is outside this test. */
'use strict';
const {chromium}=require('../phase3/node_modules/playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const source=process.env.HS_LANGUAGE_SOURCE?fs.readFileSync(process.env.HS_LANGUAGE_SOURCE,'utf8'):fs.readFileSync(path.join(root,'site-language.js'),'utf8');
const report={checks:[],errors:[],externalTranslationTested:false,physicalMobileTested:false};
function check(name,condition=true){assert.ok(condition,name);report.checks.push(name);console.log('PASS',name);}
const fixture=native=>`<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>Language fixture</title></head><body><header><select id="language"><option value="ko">한국어</option>${native?'<option value="en">English</option>':''}</select></header><main><p id="content">배우는 한국어는 보존합니다.</p><a id="next" href="/reading.html">읽기</a><a id="outside" href="https://example.org/">External</a></main>${native?'<script>window.nativeCalls=[];document.querySelector("#language").onchange=e=>nativeCalls.push(e.target.value);</script>':''}<script src="/site-language.js"></script></body></html>`;
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  for(const width of [1440,390]){
   const context=await browser.newContext({viewport:{width,height:900}}),external=[];
   await context.route('**/*',async route=>{
    const url=new URL(route.request().url());
    if(!['site.example.test','localhost'].includes(url.hostname)){external.push(url.href);return route.abort();}
    if(url.pathname==='/site-language.js')return route.fulfill({contentType:'application/javascript;charset=utf-8',body:source});
    return route.fulfill({contentType:'text/html;charset=utf-8',body:fixture(url.pathname==='/native.html')});
   });
   const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
   for(const lang of ['ko','en','ja','es','ru','zh-CN','mn','vi']){
    await page.goto(`https://site.example.test/index.html?lang=${lang}&token=DO_NOT_FORWARD#private-record`);
    assert.equal(await page.locator('#language').inputValue(),lang);
    assert.equal(await page.locator('#language option').count(),8);
    assert.equal(await page.evaluate(()=>document.documentElement.lang),lang);
    assert.equal(await page.locator('#content').getAttribute('translate'),'no');
    assert.equal(await page.locator('#content').textContent(),'배우는 한국어는 보존합니다.');
    assert.equal(new URL(await page.locator('#next').getAttribute('href')).searchParams.get('lang'),lang);
    assert.equal(await page.locator('#outside').getAttribute('href'),'https://example.org/');
    assert.equal(await page.locator('script[src*="translate.google"]').count(),0);
    const link=page.locator('#hs-public-translation');
    if(lang==='ko'){assert.equal(await link.count(),0);}else{
     const target=new URL(await link.getAttribute('href'));
     assert.equal(target.origin,'https://translate.google.com');assert.equal(target.pathname,'/translate');
     assert.equal(target.searchParams.get('tl'),lang);assert.equal(target.searchParams.get('sl'),'ko');
     assert.equal(target.searchParams.get('u'),`https://site.example.test/index.html?lang=${lang}`);
     assert.equal(await link.getAttribute('target'),'_blank');
     assert.equal(await link.getAttribute('rel'),'noopener noreferrer');
     assert.equal(await link.getAttribute('referrerpolicy'),'no-referrer');
    }
   }
   check(`${width}: eight languages, protected lesson text, safe separate translation link`);
   for(let i=0;i<3;i++)for(const lang of ['ja','vi','ko'])await page.goto(`https://site.example.test/?lang=${lang}`,{waitUntil:'domcontentloaded'});
   check(`${width}: rapid navigation never loads external translator`,external.length===0);
   await page.goto('https://site.example.test/index.html?lang=ko');
   await Promise.all([page.waitForURL(url=>url.searchParams.get('lang')==='vi'),page.locator('#language').selectOption('vi')]);
   assert.equal(await page.evaluate(()=>localStorage.getItem('hs-site-language')),'vi');
   await page.reload();assert.equal(await page.locator('#language').inputValue(),'vi');
   check(`${width}: selection navigates, saves and survives reload`);
   await page.goto('https://site.example.test/native.html?lang=en');
   assert.deepEqual(await page.evaluate(()=>nativeCalls),['en']);
   assert.equal(await page.locator('#hs-public-translation').count(),0);
   await page.locator('#language').selectOption('ko');
   assert.deepEqual(await page.evaluate(()=>nativeCalls),['en','ko']);
   assert.equal(new URL(page.url()).searchParams.get('lang'),'ko');
   check(`${width}: native bilingual course handler remains active`);
   await page.goto('http://localhost/index.html?lang=vi');
   assert.equal(await page.locator('#hs-public-translation').count(),0);
   assert.match(await page.locator('#hs-header-language-status').textContent(),/browser/);
   check(`${width}: local page gives browser translation guidance without external requests`);
   await page.goto('https://site.example.test/?lang=%3Cscript%3E');
   await page.evaluate(()=>{localStorage.clear();});await page.reload();
   assert.equal(await page.locator('#language').inputValue(),'ko');
   await page.addScriptTag({content:source});assert.equal(await page.locator('#hs-site-language-bar').count(),1);
   check(`${width}: invalid language and duplicate initialization remain safe`);
   assert.deepEqual(errors,[]);
   const observed=page.waitForEvent('pageerror');await page.evaluate(()=>setTimeout(()=>{throw Error('intentional error observation probe')},0));
   assert.match((await observed).message,/intentional error observation probe/);
   check(`${width}: unrelated JavaScript errors are not suppressed`);
   await context.close();
   assert.deepEqual(errors,['intentional error observation probe']);
  }
 }catch(e){report.errors.push(e.stack||e.message);throw e;}
 finally{await browser.close();fs.mkdirSync(path.join(root,'audit'),{recursive:true});fs.writeFileSync(path.join(root,'audit/site-language-browser.json'),JSON.stringify(report,null,2)+'\n');}
})().catch(e=>{console.error(e);process.exitCode=1});
