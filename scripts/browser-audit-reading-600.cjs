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
 // Task #46: actual 375px Chromium interaction. A desktop content audit
 // alone cannot detect the mobile level selector becoming inaccessible.
 await page.setViewportSize({width:375,height:812});
 await page.reload({waitUntil:'domcontentloaded'});
 assert.equal(await page.locator('#levels button').count(),15,'All 15 mobile levels must be available');
 assert.equal(await page.locator('#volumes button').count(),40,'Initial mobile level must list 40 books');
 await page.locator('#levels button').nth(9).click();
 assert.match(await page.locator('#libraryTitle').innerText(),/10/,'Selecting level 10 must work');
 assert.equal(await page.locator('#levels').isVisible(),false,'Selected mobile level sidebar should collapse');
 await page.locator('#changeLevel').click();
 assert.equal(await page.locator('#levels').isVisible(),true,'Change level must reopen the mobile selector');
 await page.locator('#levels button').nth(14).click();
 assert.match(await page.locator('#libraryTitle').innerText(),/15/,'Changing to level 15 must work');
 assert.equal(await page.locator('#volumes button').count(),40,'Level 15 must list 40 books');
 await page.locator('#volumes button').nth(39).click();
 assert.equal(await page.locator('#reader').isVisible(),true,'Mobile reader must open');
 assert.match(await page.locator('#readerIndex').innerText(),/LEVEL 15.*BOOK 40/);
 const correctIndices=await page.evaluate(()=>content(15,40).q.map(q=>q.correct));
 assert.equal(correctIndices.length,3,'Reading quiz must have 3 questions');
 await page.locator('#grade').click();
 assert.match(await page.locator('#result').innerText(),/0\/3/,'Unanswered mobile quiz must score zero');
 for(let i=0;i<correctIndices.length;i++)
   await page.locator('.question').nth(i).locator('.options button').nth(correctIndices[i]).click();
 await page.locator('#grade').click();
 assert.match(await page.locator('#result').innerText(),/3\/3/,'Correct mobile quiz must complete');
 assert.equal(await page.locator('.answer-evidence').count(),3,'Every mobile answer must show evidence');
 const evidence=await page.locator('.answer-evidence').allInnerTexts();
 assert.ok(evidence.every(x=>x.includes('근거:')&&x.trim().length>8),'Mobile answer evidence must be nonempty');
 const stored=await page.evaluate(()=>JSON.parse(localStorage.getItem('hs-reading-v1')||'{}')['15-40']);
 assert.equal(stored?.done,true,'Mobile quiz completion must persist locally');
 await page.reload({waitUntil:'domcontentloaded'});
 const restored=await page.evaluate(()=>JSON.parse(localStorage.getItem('hs-reading-v1')||'{}')['15-40']);
 assert.equal(restored?.done,true,'Mobile quiz completion must survive reload');
 const viewport=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));
 assert.ok(viewport.scrollWidth<=viewport.width+1,
   '375px mobile page must not overflow horizontally: '+JSON.stringify(viewport));
 assert.equal(errors.length,0,'Browser errors after mobile flow: '+errors.join('; '));
 console.log('PASS #46 375px Chromium level switch, book 40, quiz, evidence, reload and overflow');
 }finally{if(browser)await browser.close();await new Promise(ok=>server.close(ok))}
})().catch(e=>{console.error(e);process.exitCode=1});
