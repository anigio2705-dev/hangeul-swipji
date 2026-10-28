// Local HTTPS, two independent accounts and intercepted media provider. No physical call.
const path=require('path'),fs=require('fs'),os=require('os'),assert=require('assert/strict'),{spawn,spawnSync}=require('child_process');
const root=__dirname,{chromium}=require(path.join(root,'node_modules/playwright'));
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'hs-instant-')),port=30000+Math.floor(Math.random()*10000),base=`https://127.0.0.1:${port}`;
const env={...process.env,HS_STAGING_DB:path.join(tmp,'hangeul-swipji-staging/test.sqlite3'),HS_STAGING_ORIGIN:base,HS_STAGING_USER:'review',HS_STAGING_PASSWORD:'Disposable-Gate-Fixture-12345!',HS_STAGING_ADMIN_PASSWORD:'Disposable-Admin-Fixture-12345!'};delete env.HS_PHASE3_DB;
const clock=path.join(tmp,'clock');fs.writeFileSync(clock,String(Date.now()/1000));const cert=path.join(tmp,'cert'),key=path.join(tmp,'key');
assert.equal(spawnSync('openssl',['req','-x509','-newkey','rsa:2048','-nodes','-keyout',key,'-out',cert,'-days','1','-subj','/CN=localhost'],{stdio:'ignore'}).status,0);
let server,browser;const checks=[],errors=[];const check=s=>{checks.push(s);console.log('PASS',s)};
(async()=>{try{
server=spawn('python3',[path.join(root,'browser_server.py'),'--port',String(port),'--clock-file',clock,'--tls-cert',cert,'--tls-key',key],{env,stdio:['ignore','pipe','pipe']});
await new Promise((resolve,reject)=>{server.stdout.once('data',resolve);server.once('error',reject);server.once('exit',c=>reject(Error('server '+c)))});
browser=await chromium.launch({headless:true});const contexts=[];let partnerId;
for(let i=0;i<2;i++){
 const c=await browser.newContext({ignoreHTTPSErrors:true,viewport:{width:i?390:1440,height:900}});contexts.push(c);
 assert.equal((await c.request.get(base+'/',{headers:{Authorization:'Basic '+Buffer.from('review:'+env.HS_STAGING_PASSWORD).toString('base64')}})).status(),200);
 const r=await c.request.post(base+'/api/register',{headers:{Origin:base},data:{email:`instant${i}@example.test`,password:'Disposable-Password-12345!',nickname:i?'대화 파트너':'테스트 학생',role:i?'partner':'learner',adultConsent:true}});assert.equal(r.status(),200);
 if(i)partnerId=(await r.json()).user.id;
 await c.route('https://meet.jit.si/**',async route=>{const h=await route.request().allHeaders();assert.equal(h.authorization,undefined);assert.equal(h.cookie,undefined);assert.equal(h.referer,undefined);return route.fulfill({contentType:'text/html',body:'<p>Intercepted media: no real call</p>'})});
}
const approve=spawnSync('python3',['-c','import sqlite3,sys; db=sqlite3.connect(sys.argv[1]); db.execute("UPDATE users SET approved=1 WHERE id=?",(sys.argv[2],)); db.commit()',env.HS_STAGING_DB,partnerId]);assert.equal(approve.status,0);
const p=await contexts[0].newPage(),q=await contexts[1].newPage();for(const page of [p,q])page.on('pageerror',e=>errors.push(e.message));
await p.goto(base+'/index.html');await p.locator('.editorial-ctas a[href*="speaking-platform"]').click();await p.locator('#queue').waitFor();assert.equal(await p.locator('iframe').count(),0);check('home CTA uses current account; no booking, signup or automatic camera');
await p.locator('#queue').click();await p.locator('#status').filter({hasText:'접속 중인 상대'}).waitFor();check('no partner shows waiting rather than a false connection');
await contexts[1].request.post(base+'/api/logout',{headers:{Origin:base},data:{}});
await q.goto(base+'/speaking-platform.html');await q.locator('#loginBox').waitFor();await q.locator('#email').fill('instant1@example.test');await q.locator('#password').fill('Disposable-Password-12345!');await q.locator('#login button').click();await q.locator('#queue').waitFor();check('existing test account can sign in on the instant page');
await q.locator('#queue').click();await q.locator('#ready').waitFor();await p.locator('#ready').waitFor();assert.equal(await p.locator('iframe').count(),0);check('two opt-in users automatically matched without an invitation link');
await p.locator('#ready').click();await p.locator('#status').filter({hasText:'상대방의 입장 확인'}).waitFor();assert.equal(await p.locator('#start').isVisible(),false);check('room withheld until both people confirm');
await q.locator('#ready').click();await q.locator('#start').waitFor();await p.locator('#start').waitFor();await q.locator('#start').click();await p.locator('#start').click();
assert.equal(await p.locator('iframe').getAttribute('src'),await q.locator('iframe').getAttribute('src'));
await p.frameLocator('iframe').getByText('Intercepted media: no real call').waitFor();check('both account contexts open identical mocked Jitsi room without gate credentials');
assert.equal(await q.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);check('mobile390 has no horizontal overflow');
await q.locator('#stop').click();await q.locator('#queue').waitFor();await p.locator('#queue').waitFor();assert.equal(await p.locator('iframe').count(),0);check('end removes both frames and does not silently requeue');
await p.locator('#queue').click();await q.locator('#queue').click();await q.locator('#ready').waitFor();fs.writeFileSync(clock,String(Number(fs.readFileSync(clock))+61));await q.locator('#queue').waitFor();await p.locator('#queue').waitFor();check('unanswered offer and stale presence expire');
// A pagehide/pageshow cycle models bfcache suspension without destroying the document.
await p.evaluate(()=>dispatchEvent(new Event('pagehide')));
await p.evaluate(()=>dispatchEvent(new Event('pageshow')));
await p.locator('#queue').waitFor();
await p.locator('#queue').click();
await p.locator('#status').filter({hasText:'접속 중인 상대'}).waitFor();
check('pagehide/pageshow restarts status polling and allows a fresh queue join');
await p.reload();
await p.locator('#status').filter({hasText:'접속 중인 상대'}).waitFor();
check('reload restores the existing waiting state without an extra join');
await p.locator('#stop').click();
await p.locator('#queue').waitFor();
check('explicit leave clears waiting state after reload');
await p.getByRole('link',{name:'예약한 강사 수업',exact:true}).click();await p.locator('#studio-root').waitFor();check('booked class remains separately reachable');assert.deepEqual(errors,[]);
fs.writeFileSync(path.join(root,'../audit/staging9-instant-results.json'),JSON.stringify({checkedAt:new Date().toISOString(),mode:'local-https-instant-auto-matching',checks,errors,providerFrameMocked:true,actualTwoDeviceCallVerified:false,publicServerDeployed:false},null,2)+'\n');
}finally{if(browser)await browser.close();if(server)server.kill();fs.rmSync(tmp,{recursive:true,force:true});}})().catch(e=>{console.error(e);process.exitCode=1});
