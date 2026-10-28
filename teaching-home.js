/* Mount the working classroom inside the one existing homepage, without changing its styles. */
'use strict';
(async()=>{
 const host=document.getElementById('studio-root'); if(!host)return;
 try{
   const ready=await fetch('/api/integrations',{credentials:'same-origin'});if(!ready.ok)throw Error(ready.status===401?'staging-auth':'unavailable');
   const data=await ready.json();if(data.mode!=='test'||data.productionDatabaseUsed!==false)throw Error('untrusted environment');
   const response=await fetch('/phase3/shell.html');if(!response.ok)throw Error('unavailable');
   const html=await response.text(),root=host.attachShadow({mode:'open'});root.innerHTML=html;
   const script=document.createElement('script');script.src='/phase3/app.js';script.onerror=()=>{root.textContent='수업 화면을 불러오지 못했습니다. 새로고침해 주세요.'};document.body.append(script);
 }catch(e){
   host.replaceChildren();const note=document.createElement('p');note.setAttribute('role','status');note.textContent=e.message==='staging-auth'?'테스트 서버 접속 인증이 필요합니다. 수업 계정 로그인이나 화상 인증을 반복하지 마세요.':'강사 수업 연결은 통합 테스트 서버에서 확인할 수 있습니다. 무료 학습은 계속 이용할 수 있습니다. / Teaching is available on the integrated test server. Free lessons remain available.';
   const help=document.createElement('details'),title=document.createElement('summary'),code=document.createElement('code');title.textContent='통합 미리보기 실행 / Run preview';code.textContent='python3 phase3/server.py → http://127.0.0.1:8765/';help.append(title,code);host.append(note);if(e.message!=='staging-auth')host.append(help);
 }
})();
