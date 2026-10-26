/* Browser rendering coverage for every course unit in Korean and English. */
'use strict';
const {chromium}=require('playwright'),fs=require('node:fs'),http=require('node:http'),path=require('node:path'),assert=require('node:assert/strict');
const {root,courses}=require('./curriculum-source.cjs');
const mime={'.html':'text/html;charset=utf-8','.js':'text/javascript;charset=utf-8','.json':'application/json','.css':'text/css','.mp3':'audio/mpeg'};
const server=http.createServer((req,res)=>{const file=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname);if(!file.startsWith(root+path.sep)){res.writeHead(403).end();return}fs.readFile(file,(e,b)=>{if(e){res.writeHead(404).end();return}res.setHeader('Content-Type',mime[path.extname(file)]||'application/octet-stream');res.end(b)})});
(async()=>{await new Promise(r=>server.listen(0,'127.0.0.1',r));let browser;const result={units:0,languageViews:0,errors:[],screenshots:[]};
try{
 browser=await chromium.launch({headless:true});const page=await browser.newPage();const exceptions=[];page.on('pageerror',e=>exceptions.push(e.message));
 for(const course of courses){
  await page.goto('http://127.0.0.1:'+server.address().port+'/'+course+'.html',{waitUntil:'domcontentloaded'});
  const failures=await page.evaluate(()=>{
   const issues=[];
   for(const language of ['ko','en'])for(let n=0;n<50;n++){
    try{lang=language;unit=n;tab=2;render();if(!document.getElementById('content').textContent.trim())throw Error('Empty grammar');tab=3;render();if(document.querySelectorAll('#content .question').length===0&& !document.getElementById('content').textContent.includes('1.'))throw Error('Empty quiz');}
    catch(e){issues.push({language,unit:n+1,error:e.message})}
   }
   return issues;
  });
  result.units+=50;result.languageViews+=100;result.errors.push(...failures.map(x=>({course,...x})));console.log('Rendered',course,'50 units x 2 languages');
 }
 result.errors.push(...exceptions);assert.equal(result.errors.length,0,JSON.stringify(result.errors.slice(0,10)));
}finally{if(browser)await browser.close();await new Promise(r=>server.close(r));fs.mkdirSync(path.join(root,'audit'),{recursive:true});fs.writeFileSync(path.join(root,'audit/browser-lessons.json'),JSON.stringify(result,null,2)+'\n');}
})().catch(e=>{console.error(e);process.exitCode=1});
