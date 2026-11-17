'use strict';
// Real Chromium + actual local HTTP/SQLite. Only delivery of one PUT is delayed.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict');
const {spawn,spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'../..');
const {chromium}=require(path.join(root,'phase3/node_modules/playwright'));
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'hs-profile-race-'));
const env=Object.fromEntries(Object.entries(process.env).filter(([k])=>!k.startsWith('HS_')&&!k.startsWith('SUPABASE')&&!k.startsWith('STRIPE')&&k!=='DATABASE_URL'));
env.HS_PHASE3_DB=path.join(temp,'test.sqlite3');
const output=process.env.HS_RACE_OUTPUT||path.join(__dirname,'profile-races.json');
let server,browser;
const result={scope:'REAL_LOCAL_BROWSER_DELAYED_PROFILE_SAVE_ACCOUNT_BOUNDARIES',cases:[],page_errors:[]};
const password='Local-Race-Password-12345!';
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
async function signup(page,base,name){
 await page.goto(base);
 await page.getByRole('button',{name:'시작하기',exact:true}).click();
 await page.locator('#auth-form [name=email]').fill(name+'@example.test');
 await page.locator('#auth-form [name=password]').fill(password);
 await page.locator('#auth-form [name=nickname]').fill(name);
 await page.locator('#auth-form [name=role]').selectOption('learner');
 await page.locator('#auth-form [name=adultConsent]').check();
 await page.getByRole('button',{name:'테스트 계정 만들기',exact:true}).click();
 await page.locator('#auth-dialog').waitFor({state:'hidden'});
}
async function login(page,name){
 await page.getByRole('button',{name:'로그인',exact:true}).click();
 await page.locator('#auth-form [name=email]').fill(name+'@example.test');
 await page.locator('#auth-form [name=password]').fill(password);
 await page.getByRole('button',{name:'로그인',exact:true}).last().click();
 await page.locator('#auth-dialog').waitFor({state:'hidden'});
}
(async()=>{
 try{
  // Ask the OS for an unused local port through a temporary listener.
  const net=require('node:net');const listener=net.createServer();
  await new Promise(resolve=>listener.listen(0,'127.0.0.1',resolve));const port=listener.address().port;
  await new Promise(resolve=>listener.close(resolve));const base='http://127.0.0.1:'+port;
  server=spawn('python3',['phase3/server.py','--port',String(port)],{cwd:root,env,stdio:['ignore','pipe','pipe']});
  await new Promise((resolve,reject)=>{server.stdout.once('data',resolve);server.once('error',reject);server.once('exit',c=>reject(Error('server exited '+c)));});
  browser=await chromium.launch({headless:true});
  for(const scenario of ['logout_success','switch_success','switch_failure']){
   const context=await browser.newContext({viewport:{width:390,height:844}});
   await context.route('**/*',route=>new URL(route.request().url()).origin===base?route.continue():route.abort());
   const page=await context.newPage();page.setDefaultTimeout(10000);
   page.on('pageerror',error=>result.page_errors.push(error.message));
   const alice='Alice_'+scenario,bob='Bob_'+scenario,marker='Saved_'+alice;
   const other=await browser.newContext();const registration=await other.request.post(base+'/api/register',{data:{email:bob+'@example.test',password,nickname:bob,role:'learner',adultConsent:true}});
   assert.equal(registration.status(),200);await other.close();
   await signup(page,base,alice);
   await page.getByRole('button',{name:'내 프로필',exact:true}).click();
   await page.locator('#content [name=nickname]').fill(marker);
   const reached=deferred(),release=deferred();
   await page.route('**/api/profile',async route=>{
    if(route.request().method()!=='PUT')return route.continue();
    // Commit first in the real server. Only the browser response is withheld.
    const actual=await route.fetch();assert.equal(actual.status(),200);
    reached.resolve();await release.promise;
    if(scenario==='switch_failure')await route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({error:'OLD_ACCOUNT_DELAYED_FAILURE'})});
    else await route.fulfill({response:actual});
   });
   await page.getByRole('button',{name:'프로필 저장',exact:true}).click();await reached.promise;
   await page.getByRole('button',{name:'로그아웃',exact:true}).click();
   await page.locator('#account').getByRole('button',{name:'로그인',exact:true}).waitFor();
   if(scenario!=='logout_success')await login(page,bob);
   const finished=page.waitForEvent('requestfinished',request=>request.url()===base+'/api/profile'&&request.method()==='PUT');
   release.resolve();await finished;
   await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
   const account=await page.locator('#account').innerText();
   const content=await page.locator('#content').innerText();
   const message=await page.locator('#message').innerText();
   const me=await context.request.get(base+'/api/me');
   const violations=[];
   if(scenario==='logout_success'){
    if(me.status()!==401)violations.push('server session must stay logged out');
    if(!(await page.locator('#account').getByRole('button',{name:'로그인',exact:true}).count()))violations.push('old response resurrected signed-in UI');
   }else{
    const user=(await me.json()).user;
    if(me.status()!==200||user.nickname!==bob)violations.push('server must stay on Bob');
    if(!account.includes(bob)||account.includes(alice))violations.push('old response replaced Bob in account UI');
   }
   if(content.includes(marker)||account.includes(marker))violations.push('old profile data displayed after account transition');
   if(message.includes('OLD_ACCOUNT_DELAYED_FAILURE')||message.includes('프로필을 저장했습니다'))violations.push('old save success/error displayed for new account');
   const db=spawnSync('python3',['-c',"import sqlite3,json,sys; c=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True); print(json.dumps(c.execute('SELECT nickname FROM users WHERE email=?',(sys.argv[2],)).fetchone()))",env.HS_PHASE3_DB,alice.toLowerCase()+'@example.test'],{encoding:'utf8'});
   assert.equal(db.status,0,db.stderr);assert.deepEqual(JSON.parse(db.stdout),[marker]);
   result.cases.push({scenario,status:violations.length?'FAIL':'PASS',violations,server_session_status:me.status(),account_text:account,old_profile_committed_to_correct_account:true});
   await context.close();
  }
  assert.equal(result.page_errors.length,0);
  result.status=result.cases.every(c=>c.status==='PASS')?'PASS':'FAIL';
  if(result.status==='FAIL')process.exitCode=1;
 }catch(error){result.status='ERROR_OR_BLOCKED';result.error=String(error);result.stack=error.stack;process.exitCode=1;}
 finally{
  if(browser)await browser.close();
  if(server&&server.exitCode===null){const exited=new Promise(resolve=>server.once('exit',resolve));server.kill('SIGTERM');await exited;}
  fs.writeFileSync(output,JSON.stringify(result,null,2)+'\n');fs.rmSync(temp,{recursive:true,force:true});console.log(JSON.stringify(result,null,2));
 }
})();
