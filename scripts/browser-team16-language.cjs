/* Actual desktop/mobile Chromium verification of the approved eight site languages. */
'use strict';
const {chromium}=require('playwright');
const http=require('node:http'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const mime={'.html':'text/html;charset=utf-8','.js':'text/javascript;charset=utf-8','.css':'text/css;charset=utf-8'};
const expected=['ko','en','ja','es','zh-CN','ru','mn','vi'];
const server=http.createServer((req,res)=>{
  let pathname;
  try{pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname)}
  catch(_){res.writeHead(400).end();return}
  const file=path.resolve(root,'.'+pathname);
  if(!file.startsWith(root+path.sep)){res.writeHead(403).end();return}
  fs.stat(file,(err,stat)=>{
    if(err||!stat.isFile()){res.writeHead(404).end();return}
    res.setHeader('Content-Type',mime[path.extname(file)]||'application/octet-stream');
    fs.createReadStream(file).pipe(res);
  });
});
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const base='http://127.0.0.1:'+server.address().port;
  let browser;
  try{
    browser=await chromium.launch({headless:true});
    for(const profile of [
      {name:'desktop',viewport:{width:1440,height:900}},
      {name:'mobile',viewport:{width:390,height:844},isMobile:true,hasTouch:true}
    ]){
      const context=await browser.newContext(profile),page=await context.newPage();
      const errors=[];page.on('pageerror',e=>errors.push(e.message));
      await page.route('https://translate.google.com/**',r=>r.abort());
      await page.goto(base+'/index.html?lang=unsupported',{waitUntil:'domcontentloaded'});
      await page.locator('#language option[value="vi"]').waitFor({state:'attached'});
      const options=await page.locator('#language option').evaluateAll(els=>els.map(e=>e.value));
      assert.deepEqual(options,expected,profile.name+' language menu');
      assert.equal(await page.locator('#language').inputValue(),'ko',profile.name+' invalid query fallback');
      await page.locator('#language').selectOption('es');
      await page.waitForURL(url=>url.searchParams.get('lang')==='es');
      assert.equal(await page.evaluate(()=>localStorage.getItem('hs-site-language')),'es',profile.name+' saved locale');
      await page.goto(base+'/index.html?lang=unsupported',{waitUntil:'domcontentloaded'});
      await page.locator('#language option[value="vi"]').waitFor({state:'attached'});
      assert.equal(await page.locator('#language').inputValue(),'es',profile.name+' valid saved fallback');
      await page.evaluate(()=>{
        localStorage.setItem('hs-site-language','fr');
        localStorage.setItem('hs-language','de');
      });
      await page.goto(base+'/index.html?lang=unsupported',{waitUntil:'domcontentloaded'});
      await page.locator('#language option[value="vi"]').waitFor({state:'attached'});
      assert.equal(await page.locator('#language').inputValue(),'ko',profile.name+' invalid saved fallback');
      await page.goto(base+'/global-language.html?lang=ko',{waitUntil:'domcontentloaded'});
      await page.locator('#from option[value="vi"]').waitFor({state:'attached'});
      for(const id of ['from','to']){
        const labOptions=await page.locator('#'+id+' option').evaluateAll(els=>els.map(e=>e.value));
        assert.deepEqual(labOptions,expected,profile.name+' translator '+id+' options');
      }
      assert.equal(errors.length,0,profile.name+' JS errors: '+errors.join('; '));
      console.log('PASS team16',profile.name,'eight options, selection, persistence and fallback');
      await context.close();
    }
  }finally{
    if(browser)await browser.close();
    await new Promise(resolve=>server.close(resolve));
  }
})().catch(e=>{console.error(e);process.exitCode=1});
