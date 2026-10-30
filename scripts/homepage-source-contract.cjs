'use strict';
// Exact, reversible UI additions only. This is a staging audit contract, NOT deployment approval.
const teaching=[
  '<a href="#teaching-platform">강사 수업 · 테스트</a>',
  '<section id="teaching-platform" class="shell" aria-label="전문 교육과 강사 수업"><h2>혼자 배운 한국어, 함께 써 보세요.</h2><p>무료 학습부터 전문 수업, 과제와 피드백까지 한글쉽지에서 이어집니다.</p><div id="studio-root"><p id="studio-status" role="status">수업 공간을 확인하고 있습니다…</p></div></section>',
  '<script src="./teaching-home.js?v=20261027-global" defer></script>'
];
const handoff='<div class="shell" data-team12-handoff></div><script src="./scripts/team12_learning_handoff.js" defer></script>';
// Reviewed staging-only layout deltas; every byte outside these exact spans is immutable.
const layout=[
  ['.editorial-landing{position:relative;min-height:640px','.editorial-landing{position:relative;min-height:760px'],
  ['.editorial-image{position:relative;min-height:640px','.editorial-image{position:relative;min-height:760px'],
  ['.editorial-content{padding:56px clamp(28px,5vw,100px) 50px','.editorial-content{padding:90px clamp(28px,5vw,100px) 65px'],
  ['.editorial-steps{margin-top:38px;padding-top:24px','.editorial-steps{margin-top:65px;padding-top:24px']
];
function replaceExactlyOnce(text,from,to=''){
  const first=text.indexOf(from);
  if(first<0||text.indexOf(from,first+from.length)!==-1)return null;
  return text.slice(0,first)+to+text.slice(first+from.length);
}
function stripTeaching(text){
  for(const token of teaching){text=replaceExactlyOnce(text,token);if(text===null)return null;}
  return text;
}
function validateHomepage(homepage,original){
  if(homepage===original)return {ok:true,variant:'original'};
  const basic=stripTeaching(homepage);
  if(basic===original)return {ok:true,variant:'teaching-integration'};
  let candidate=replaceExactlyOnce(homepage,handoff);
  if(candidate===null)return {ok:false,variant:'unrecognized',reason:'Staging handoff missing or duplicated'};
  for(const [stage,source] of layout){
    candidate=replaceExactlyOnce(candidate,stage,source);
    if(candidate===null)return {ok:false,variant:'unrecognized',reason:'Staging layout delta missing or duplicated'};
  }
  candidate=stripTeaching(candidate);
  if(candidate===original)return {ok:true,variant:'staging-handoff-and-layout'};
  return {ok:false,variant:'unrecognized',reason:'Homepage differs outside exact reversible additions'};
}
module.exports={validateHomepage};
