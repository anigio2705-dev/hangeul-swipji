/* Hangeul Swipji - active recall companion for the seven 50-unit courses. */
(function(){
"use strict";
const course=(location.pathname.split("/").pop()||"intro.html").replace(".html","");
const key="hs-recall-"+course+(course==="intro"?"-foundations-v2":"-v1");
const $=id=>document.getElementById(id);
const safeLoad=()=>{try{const x=JSON.parse(localStorage.getItem(key)||"{}");return x&&typeof x==="object"&&!Array.isArray(x)?x:{}}catch{return {}}};
let records=safeLoad(),shown=-1,attempted=false;
function txt(ko,en){return lang==="ko"?ko:en}
function normalize(s){return String(s||"").normalize("NFC").toLowerCase().replace(/[\s.,!?~"'‘’“”]/g,"")}
function getTarget(u){if(u.recall)return u.recall;const options=(u.sent||[]).filter(x=>Array.isArray(x)&&x[0]&&x[1]);return options.length?options[Math.min(1,options.length-1)]:null}
function due(rec){return !rec||!rec.next||Date.now()>=rec.next}
function updateStats(){
const all=units.map((_,i)=>records[i]).filter(Boolean);
const mastered=all.filter(x=>x.success>=2).length;
const dueCount=units.filter((_,i)=>records[i]&&due(records[i])).length;
$("recallStats").textContent=txt("복습 대상 ","Due for review: ")+dueCount+" · "+txt("2회 이상 성공 ","Mastered (2+ successful recalls): ")+mastered+" / "+units.length;
}
function save(){try{localStorage.setItem(key,JSON.stringify(records))}catch{}updateStats()}
function renderRecall(){
if(typeof units==="undefined"||typeof unit==="undefined")return;
const u=units[unit],target=getTarget(u),box=$("recallPanel");
if(!box)return;
box.hidden=!target;
if(!target)return;
shown=unit;attempted=false;
$("recallHeading").textContent=u.recall?txt("글자를 합쳐 써 보기","Build and write a block"):txt("기억하고 직접 말하기","Recall and produce Korean");
$("recallHelp").textContent=u.recall?txt("자음과 모음을 합쳐 글자를 입력하세요. 이 문제는 발음 평가가 아닙니다.","Combine the letters and type the block. This is not a pronunciation test."):txt("뜻을 보고 한국어 문장을 직접 입력하세요. 띄어쓰기와 문장부호는 채점에서 제외합니다.","Read the meaning, then type the Korean sentence from memory. Spacing and punctuation are ignored in grading.");
$("recallPrompt").textContent=target[1];
$("recallAnswer").value="";
$("recallAnswer").placeholder=u.recall?txt("합친 글자를 입력하세요","Type the combined block"):txt("한국어 문장을 입력하세요","Type the Korean sentence");
$("recallFeedback").textContent="";
$("recallCheck").textContent=txt("내 답 확인하기","Check my answer");
$("recallReveal").textContent=txt("모범 답안 보기","Show model answer");
$("recallDue").textContent=records[unit]?(due(records[unit])?txt("지금 복습할 차례입니다.","Due for review now."):txt("다음 복습 예정: ","Next review: ")+new Date(records[unit].next).toLocaleDateString()):txt("첫 연습입니다.","First practice.");
$("recallDue").style.color=due(records[unit])?"#b2543e":"#25846e";
updateStats();
}
function grade(){
const target=getTarget(units[unit]);if(!target||shown!==unit)return;
const typed=$("recallAnswer").value.trim();
if(!typed){$("recallFeedback").textContent=txt("먼저 답을 입력하세요.","Enter an answer first.");return}
const correct=normalize(typed)===normalize(target[0]);
const old=records[unit]||{success:0,attempts:0};
const success=correct?(old.success||0)+1:0;
const intervals=[1,3,7,14,30];
const days=correct?intervals[Math.min(success-1,intervals.length-1)]:0;
records[unit]={success,attempts:(old.attempts||0)+1,lastCorrect:correct,last:Date.now(),next:Date.now()+(days?days*86400000:0)};
attempted=true;save();
$("recallFeedback").textContent=(correct?txt("정답입니다! ","Correct! "):txt("다시 연습하세요. ","Try again. "))+txt("모범 답안: ","Model: ")+target[0]+" · "+(correct?txt(days+"일 후 복습 예정", "Review in "+days+" day(s)"):txt("이 표현은 복습 대상으로 남습니다.","This expression remains due for review."));
$("recallDue").textContent=correct?txt("다음 복습: ","Next review: ")+new Date(records[unit].next).toLocaleDateString():txt("지금 다시 연습하세요.","Review again now.");
}
function reveal(){const target=getTarget(units[unit]);if(!target)return;$("recallFeedback").textContent=txt("모범 답안: ","Model answer: ")+target[0]+txt(" · 답안을 본 후에는 다시 입력해 보세요."," · Try typing it again without looking.")}
function findDue(){const i=units.findIndex((_,i)=>records[i]&&due(records[i]));if(i<0){$("recallFeedback").textContent=txt("현재 복습할 기록이 없습니다. 새로운 단원을 공부하세요.","No recorded reviews due. Study a new unit.");return}unit=i;render();$("recallPanel").scrollIntoView({behavior:"smooth",block:"start"})}
function init(){
const panel=$("recallPanel");if(!panel)return;
$("recallCheck").addEventListener("click",grade);
$("recallReveal").addEventListener("click",reveal);
$("recallReview").addEventListener("click",findDue);
$("recallAnswer").addEventListener("keydown",e=>{if(e.key==="Enter"){e.preventDefault();grade()}});
const original=window.render;
if(typeof original==="function"){window.render=function(){original.apply(this,arguments);renderRecall()}}
renderRecall();
}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);else init();
})();