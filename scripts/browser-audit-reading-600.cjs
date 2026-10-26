/* Exercise all 600 reading entries in Chromium, not just the page shell.
 * npm install --no-save playwright@1.58.2 && npx playwright install chromium
 * node scripts/browser-audit-reading-600.cjs
 */
'use strict';
const {chromium}=require('playwright');
const http=require('node:http'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const server=http.createServer((req,res)=>{const name=new URL(req.url,'http://localhost').pathname;const file=path.resolve(root,'.'+name);if(!file.startsWith(root+path.sep)){res.writeHead(403).end();return}fs.readFile(file,(err,data)=>{if(err){res.writeHead(404).end();return}res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':'text/html;charset=utf-8');res.end(data)})});
(async()=>{
 await new Promise(ok=>server.listen(0,'127.0.0.1',ok));let browser;
 try{
 browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:1280,height:800}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:'+server.address().port+'/reading.html',{waitUntil:'domcontentloaded'});
 const result=await page.evaluate(()=>{
   const failures=[];let count=0,original=0,generated=0;
   for(let l=1;l<=15;l++)for(let b=1;b<=40;b++){
     try{
       const item=content(l,b);count++;if(item.original)original++;else generated++;
       if(!item.title||!Array.isArray(item.paragraphs)||!item.paragraphs.length||item.paragraphs.some(p=>!String(p).trim()))throw Error('Missing title or paragraph');
       if(!Array.isArray(item.translations)||item.translations.length!==item.paragraphs.length)throw Error('Translation alignment');
       if(!Array.isArray(item.q)||!item.q.length)throw Error('Missing quiz');
       for(let i=0;i<item.q.length;i++){const q=item.q[i];if(!q.q||!Array.isArray(q.options)||q.options.length<2||!Number.isInteger(q.correct)||q.correct<0||q.correct>=q.options.length)throw Error('Malformed quiz '+i);if(new Set(q.options).size!==q.options.length)throw Error('Duplicate choices '+i)}
     }catch(e){failures.push({level:l,book:b,error:e.message})}
   }
   return {count,original,generated,failures};
 });
 assert.equal(result.count,600,'Expected 600 reading entries');
 assert.equal(result.failures.length,0,'Reading errors: '+JSON.stringify(result.failures.slice(0,20)));
 assert.equal(errors.length,0,'Browser errors: '+errors.join('; '));
 console.log('PASS reading 600 browser content+quiz audit',JSON.stringify(result));
 }finally{if(browser)await browser.close();await new Promise(ok=>server.close(ok))}
})().catch(e=>{console.error(e);process.exitCode=1});
