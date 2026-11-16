'use strict';
// API creates disposable fixtures; actual Chromium exercises statement UI.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict');
const {spawn,spawnSync}=require('node:child_process');
const root=process.env.HS_REVIEW_SOURCE||path.resolve(__dirname,'../hangeul-isolated-review-20261117');
const {chromium}=require(path.join(root,'phase3/node_modules/playwright'));
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'hs-independent-dispute-'));const port=32568,base='http://127.0.0.1:'+port;
const env=Object.fromEntries(Object.entries(process.env).filter(([k])=>!k.startsWith('HS_')&&!k.startsWith('SUPABASE')&&!k.startsWith('STRIPE')&&k!=='DATABASE_URL'));
Object.assign(env,{HS_PHASE3_DB:path.join(temp,'test.sqlite3'),HS_PHASE3_ADMIN_PASSWORD:'Independent-Admin-Fixture-12345!'});
let server,browser;const result={scope:'INDEPENDENT_REAL_STATEMENT_UI_AND_NEGATIVE_AUTHORIZATION',checks:[],page_errors:[]};
async function request(context,url,data,method){const r=await context.request.fetch(base+url,{method:method||(data?'POST':'GET'),data});const v=await r.json();assert.equal(r.status(),200,JSON.stringify(v));return v;}
(async()=>{
 try{
  let created=spawnSync('python3',['phase3/server.py','--create-admin','admin@example.test'],{cwd:root,env,encoding:'utf8'});assert.equal(created.status,0,created.stderr);
  server=spawn('python3',['phase3/server.py','--port',String(port)],{cwd:root,env,stdio:['ignore','pipe','pipe']});
  await new Promise((resolve,reject)=>{server.stdout.once('data',resolve);server.once('error',reject);server.once('exit',code=>reject(Error('server exited '+code)));});
  browser=await chromium.launch({headless:true});
  const contexts=await Promise.all([0,1,2,3].map(()=>browser.newContext()));const [tc,lc,ac,oc]=contexts;
  for(const c of contexts)await c.route('**/*',route=>new URL(route.request().url()).origin===base?route.continue():route.abort());
  let teacher,learner;
  for(const [c,name,role]of[[tc,'teacher','teacher'],[lc,'learner','learner'],[oc,'outsider','learner']]){
   const x=await request(c,'/api/register',{email:name+'@example.test',password:'Independent-Test-Password-12345!',nickname:name,role,adultConsent:true});if(role==='teacher')teacher=x.user;else if(name==='learner')learner=x.user;
  }
  await request(ac,'/api/login',{email:'admin@example.test',password:env.HS_PHASE3_ADMIN_PASSWORD});
  await request(ac,'/api/admin/verify',{userId:teacher.id,approved:true,reason:'Independent fixture approval only, no real qualifications.'});
  const now=Date.now()/1000,slot=await request(tc,'/api/availability',{start:now+600,end:now+4200}),units=await request(lc,'/api/units');
  const booking=await request(lc,'/api/bookings',{teacherId:teacher.id,slotId:slot.slotId,unitId:units.units[0].id});
  await request(lc,`/api/bookings/${booking.bookingId}/pay-test`,{});
  const dispute=await request(lc,`/api/bookings/${booking.bookingId}/dispute`,{category:'refund',reason:'Independent learner original statement.'});
  const endpoint=`/api/bookings/${booking.bookingId}/disputes/${dispute.disputeId}/statements`;
  const outside=await oc.request.get(base+endpoint);assert.equal(outside.status(),403);result.checks.push('unrelated account GET403 on actual statement endpoint');
  const teacherPage=await tc.newPage();teacherPage.on('pageerror',e=>result.page_errors.push(e.message));teacherPage.setDefaultTimeout(10000);
  await teacherPage.goto(base);await teacherPage.getByRole('button',{name:'내 수업',exact:true}).click();
  await teacherPage.getByRole('button',{name:'신고 진술 확인·추가',exact:true}).click();
  await teacherPage.getByRole('heading',{name:'신고 진술 기록',exact:true}).waitFor();
  assert((await teacherPage.locator('#detail').innerText()).includes('Independent learner original statement.'));
  await teacherPage.locator('#detail textarea[name=text]').fill('Independent teacher UI counterpart statement <script>marker</script>.');
  await teacherPage.getByRole('button',{name:'내 진술 저장',exact:true}).click();await teacherPage.locator('#detail-dialog').waitFor({state:'hidden'});
  const saved=await request(tc,endpoint);assert(saved.statements.some(s=>s.authorId===teacher.id&&s.text.includes('Independent teacher UI')));result.checks.push('teacher reads original and saves own statement through actual UI');
  await teacherPage.reload();await teacherPage.getByRole('button',{name:'내 수업',exact:true}).click();await teacherPage.getByRole('button',{name:'신고 진술 확인·추가',exact:true}).click();
  await teacherPage.getByRole('heading',{name:'신고 진술 기록',exact:true}).waitFor();
  assert((await teacherPage.locator('#detail').innerText()).includes('<script>marker</script>'));assert.equal(await teacherPage.locator('#detail script').count(),0);result.checks.push('saved text survives reload and markup stays text');
  await teacherPage.locator('#close-detail').click();
  const adminPage=await ac.newPage();adminPage.setDefaultTimeout(10000);adminPage.on('pageerror',e=>result.page_errors.push(e.message));await adminPage.goto(base);await adminPage.getByRole('button',{name:'운영 관리',exact:true}).click();
  await adminPage.getByRole('button',{name:'진술 확인',exact:true}).click();await adminPage.getByRole('heading',{name:'신고 진술 기록',exact:true}).waitFor();
  assert((await adminPage.locator('#detail').innerText()).includes('Independent teacher UI'));assert.equal(await adminPage.getByRole('button',{name:'내 진술 저장',exact:true}).count(),0);assert.equal(await adminPage.locator('#detail textarea').count(),0);result.checks.push('admin actual UI is read-only statement viewer');
  const forbidden=await ac.request.post(base+endpoint,{data:{text:'Admin cannot impersonate a participant.'}});assert.equal(forbidden.status(),403);result.checks.push('admin direct POST403 even with visible statement access');
  let release,entered;const routed=new Promise(r=>entered=r),barrier=new Promise(r=>release=r);
  await tc.route(base+endpoint,async route=>{const response=await route.fetch();entered();await barrier;await route.fulfill({response});});
  await teacherPage.getByRole('button',{name:'신고 진술 확인·추가',exact:true}).click();await routed;
  await teacherPage.getByRole('button',{name:'로그아웃',exact:true}).click();release();
  await teacherPage.waitForFunction(()=>!document.querySelector('#studio-root').shadowRoot.querySelector('#detail-dialog').open);
  assert.equal(await teacherPage.locator('#detail-dialog[open]').count(),0);result.checks.push('late statement response does not open dialog after actual logout');
  assert.equal(result.page_errors.length,0,JSON.stringify(result.page_errors));result.status='PASS_SCOPED_STATEMENT_UI';
 }catch(error){result.status='FAIL_OR_BLOCKED';result.error=String(error);result.stack=error.stack;process.exitCode=1;}
 finally{
  if(browser)await browser.close();if(server){server.kill('SIGTERM');await new Promise(resolve=>server.once('exit',resolve));}
  fs.writeFileSync(path.join(__dirname,'DISPUTE_BROWSER_RESULTS.json'),JSON.stringify(result,null,2)+'\n');fs.rmSync(temp,{recursive:true,force:true});console.log(JSON.stringify(result,null,2));
 }
})();
