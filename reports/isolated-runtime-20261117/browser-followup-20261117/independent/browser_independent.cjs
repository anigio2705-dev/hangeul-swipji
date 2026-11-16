'use strict';
// Independent real browser profile persistence/isolation, synthetic users only.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict');
const {spawn,spawnSync}=require('node:child_process');
const root=process.env.HS_REVIEW_SOURCE||path.resolve(__dirname,'../hangeul-isolated-review-20261117');
const {chromium}=require(path.join(root,'phase3/node_modules/playwright'));
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'hs-independent-ui-'));
const port=32567,base='http://127.0.0.1:'+port;
const env=Object.fromEntries(Object.entries(process.env).filter(([k])=>!k.startsWith('HS_')&&!k.startsWith('SUPABASE')&&!k.startsWith('STRIPE')&&k!=='DATABASE_URL'));
env.HS_PHASE3_DB=path.join(temp,'test.sqlite3');
let server,browser;const result={scope:'INDEPENDENT_REAL_CHROMIUM_LOCAL_PROFILE_PERSISTENCE_AND_ACCOUNT_ISOLATION',checks:[],external_blocked:[],page_errors:[]};
async function signup(page,name){
 await page.goto(base);await page.getByRole('button',{name:'시작하기',exact:true}).click();
 await page.locator('#auth-form [name=email]').fill(name+'@example.test');
 await page.locator('#auth-form [name=password]').fill('Independent-Test-Password-12345!');
 await page.locator('#auth-form [name=nickname]').fill(name);
 await page.locator('#auth-form [name=role]').selectOption('learner');
 await page.locator('#auth-form [name=adultConsent]').check();
 await page.getByRole('button',{name:'테스트 계정 만들기',exact:true}).click();
 await page.locator('#auth-dialog').waitFor({state:'hidden'});
}
(async()=>{
 try{
  server=spawn('python3',['phase3/server.py','--port',String(port)],{cwd:root,env,stdio:['ignore','pipe','pipe']});
  await new Promise((resolve,reject)=>{server.stdout.once('data',resolve);server.once('error',reject);server.once('exit',code=>reject(Error('server exited '+code)));});
  browser=await chromium.launch({headless:true});
  const contexts=await Promise.all([0,1].map(()=>browser.newContext({viewport:{width:1440,height:1000}})));
  for(const context of contexts)await context.route('**/*',route=>new URL(route.request().url()).origin===base?route.continue():(result.external_blocked.push(route.request().url()),route.abort()));
  const [alice,bob]=await Promise.all(contexts.map(c=>c.newPage()));
  for(const page of [alice,bob]){page.setDefaultTimeout(10000);page.on('pageerror',error=>result.page_errors.push(error.message));}
  await signup(alice,'IndependentAlice');await signup(bob,'IndependentBob');result.checks.push('two real UI signups in separate browser contexts');
  await alice.getByRole('button',{name:'내 프로필',exact:true}).click();
  await alice.locator('#content [name=nickname]').fill('Alice persistent marker');
  await alice.getByRole('button',{name:'프로필 저장',exact:true}).click();
  await alice.waitForFunction(()=>document.querySelector('#studio-root').shadowRoot.querySelector('#content [name=nickname]')?.value==='Alice persistent marker');
  await alice.reload();await alice.getByRole('button',{name:'내 프로필',exact:true}).click();
  assert.equal(await alice.locator('#content [name=nickname]').inputValue(),'Alice persistent marker');result.checks.push('UI edit saved and visible after real reload');
  await bob.getByRole('button',{name:'내 프로필',exact:true}).click();
  assert.equal(await bob.locator('#content [name=nickname]').inputValue(),'IndependentBob');
  assert(!(await bob.locator('#content').innerText()).includes('Alice persistent marker'));result.checks.push('other browser account profile not overwritten');
  const a=await contexts[0].request.get(base+'/api/me'),b=await contexts[1].request.get(base+'/api/me');
  assert.equal(a.status(),200);assert.equal(b.status(),200);
  const am=await a.json(),bm=await b.json();assert.notEqual(am.user.id,bm.user.id);assert.equal(am.user.nickname,'Alice persistent marker');assert.equal(bm.user.nickname,'IndependentBob');result.checks.push('same actual UI sessions API readback agrees');
  const direct=spawnSync('python3',['-c',"import sqlite3,json,sys; c=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True); print(json.dumps(c.execute('SELECT email,nickname FROM users ORDER BY email').fetchall()))",env.HS_PHASE3_DB],{encoding:'utf8'});
  assert.equal(direct.status,0,direct.stderr);assert.deepEqual(JSON.parse(direct.stdout),[['independentalice@example.test','Alice persistent marker'],['independentbob@example.test','IndependentBob']]);result.checks.push('read-only SQLite oracle agrees with both UI accounts');
  await alice.screenshot({path:path.join(__dirname,'independent-desktop.png'),fullPage:true});
  await alice.setViewportSize({width:390,height:844});await alice.screenshot({path:path.join(__dirname,'independent-mobile.png'),fullPage:true});
  const overflow=await alice.evaluate(()=>({width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth}));
  assert(overflow.scroll<=overflow.width+1,JSON.stringify(overflow));result.checks.push('390px whole document no horizontal overflow');
  assert.equal(result.page_errors.length,0,JSON.stringify(result.page_errors));result.status='PASS_SCOPED_REAL_UI';
 }catch(error){result.status='FAIL_OR_BLOCKED';result.error=String(error);result.stack=error.stack;process.exitCode=1;}
 finally{
  if(browser)await browser.close();
  if(server){server.kill('SIGTERM');await new Promise(resolve=>server.once('exit',resolve));}
  fs.writeFileSync(path.join(__dirname,'BROWSER_RESULTS.json'),JSON.stringify(result,null,2)+'\n');
  fs.rmSync(temp,{recursive:true,force:true});console.log(JSON.stringify(result,null,2));
 }
})();
