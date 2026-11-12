(() => {
  'use strict';
  const $=id=>document.getElementById(id),key='hs-audio-review-v1',weekScope=new URLSearchParams(location.search).get('scope')==='week';if(weekScope)$('filter').value='week';let report,manifest,notes={},decisions={};
  const state=globalThis.HangulAudioReviewState,decisionKey='hs-audio-final-review-v1',candidates=new Map();
  try{const v=JSON.parse(localStorage.getItem(decisionKey)||'{}');if(v&&typeof v==='object'&&!Array.isArray(v))decisions=v;}catch(_){}
  const safeSrc=src=>typeof src==='string'&&src.trim()&&!/^(?:blob|data|javascript):/i.test(src.trim());
  const recordings=()=>Array.isArray(manifest.recordings)?manifest.recordings:[];
  function original(source,text){
    const matches=source?recordings().filter(x=>x.text===text&&x.src===source.src&&!x.retiredSynthetic&&x.kind==='human'):[];
    const match=matches.length===1?matches[0]:null;
    const valid=source&&source.kind==='human'&&!source.retiredSynthetic&&safeSrc(source.src)&&match&&/^[a-f0-9]{64}$/i.test(match.sha256||'')&&(!source.sha256||source.sha256===match.sha256);
    return {text,src:source&&safeSrc(source.src)?source.src:'',sha256:valid?match.sha256:'',kind:valid?'human':'',status:'pending',reviewer:'',reviewedAt:''};
  }
  function countDecisions(){const n=Object.values(decisions).filter(x=>x&&x.decision==='approved').length;$('save-status').textContent=`로컬 승인 결정 ${n}개 · 사이트 공식 승인과 별개입니다.`;}
  function saveDecisions(){try{localStorage.setItem(decisionKey,JSON.stringify(decisions));countDecisions();}catch(_){$('save-status').textContent='결정을 저장할 수 없습니다. 변경안을 내보내세요.';}}
  function finalReview(row,item,source,audio,select,hint){
    const base=original(source,item.text),id=JSON.stringify([item.text,base.src]);let saved=decisions[id];
    let active=candidates.get(id),record=active?state.replaceCandidate(base,active):base,listened='',generation=0;
    const reviewer=el('input');reviewer.placeholder='검토자 이름';reviewer.setAttribute('aria-label',item.text+' 검토자 이름');reviewer.value=saved&&typeof saved.reviewer==='string'?saved.reviewer:'';
    const status=el('p',saved?`저장된 로컬 결정: ${saved.decision}${saved.candidate?' · 같은 해시의 후보 파일을 다시 선택해야 재생·새 승인할 수 있습니다.':''}`:'로컬 최종 결정: 미결정');
    const confirmLabel=el('label',' 사람이 직접 녹음한 파일임을 확인합니다 '),confirm=el('input');confirm.type='checkbox';confirmLabel.prepend(confirm);
    const file=el('input');file.type='file';file.accept='audio/*';file.setAttribute('aria-label',item.text+' 사람 녹음 교체 파일');
    const cancel=el('button','후보 취소');cancel.type='button';
    const buttons=[];
    const ready=()=>{buttons.forEach(([button,value])=>{button.disabled=value==='approved'&&(!record.sha256||record.kind!=='human'||!listened||!reviewer.value.trim()||(!active&&!!(saved&&saved.candidate)));});};
    const reset=()=>{listened='';audio.pause();select.disabled=true;ready();};
    const apply=()=>{reset();if(active){record=state.replaceCandidate(base,active);audio.src=active.src;}else{record={...base};if(base.src)audio.src=base.src;else audio.removeAttribute('src');}audio.load();ready();};
    const persist=(decision,next)=>{saved=decisions[id]={text:item.text,original:{src:base.src,sha256:base.sha256},candidate:active?{filename:active.filename,sha256:active.sha256}:null,decision,reviewer:reviewer.value.trim(),decidedAt:new Date().toISOString(),reviewedAt:next.reviewedAt};saveDecisions();};
    for(const [value,title] of [['approved','최종 승인'],['rerecord','재녹음 필요'],['uncertain','판단 보류']]){
      const button=el('button',title);button.type='button';buttons.push([button,value]);button.onclick=()=>{try{record=state.decide(record,value,reviewer.value,listened);persist(value,record);status.textContent='로컬 최종 결정: '+title+' · 공식 반영 아님';}catch(_){status.textContent='현재 사람 녹음을 끝까지 듣고 검토자 이름을 입력하세요.';}ready();};row.append(button);
    }
    reviewer.oninput=ready;
    const ended=audio.onended,error=audio.onerror;
    audio.onended=()=>{if(ended)ended();try{listened=state.recordingKey(record.text,record.sha256);}catch(_){listened='';}ready();};
    audio.onerror=()=>{reset();if(error)error();};
    file.onchange=async()=>{
      const ticket=++generation,chosen=file.files&&file.files[0];reset();
      if(!chosen||!chosen.size||!chosen.type.startsWith('audio/')||!confirm.checked){status.textContent='비어 있지 않은 오디오 파일과 사람 녹음 확인이 필요합니다.';file.value='';return;}
      try{
        const digest=await crypto.subtle.digest('SHA-256',await chosen.arrayBuffer());
        if(ticket!==generation||!row.isConnected)return;
        if(!confirm.checked)throw Error();
        const sha256=Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,'0')).join('');
        if(!active&&saved&&saved.candidate&&saved.candidate.sha256!==sha256){status.textContent='저장된 후보와 해시가 다릅니다. 후보 취소 후 새 변경안을 선택하세요.';file.value='';return;}
        const next={src:URL.createObjectURL(chosen),sha256,kind:'human',filename:chosen.name};
        if(active)URL.revokeObjectURL(active.src);active=next;candidates.set(id,active);apply();persist('pending',record);status.textContent='사람 녹음 교체 후보 · 다시 끝까지 듣고 결정하세요.';
      }catch(_){status.textContent='후보 해시를 계산할 수 없습니다. 파일과 사람 녹음 확인을 점검하세요.';}
    };
    cancel.onclick=()=>{generation++;if(active)URL.revokeObjectURL(active.src);candidates.delete(id);active=null;file.value='';apply();persist('pending',record);status.textContent='원본으로 돌아왔습니다. 다시 끝까지 들어야 합니다.';};
    row.append(reviewer,status,confirmLabel,file,cancel);
    if(active)apply();else if(saved&&saved.candidate){audio.removeAttribute('src');audio.load();}
    ready();
  }
  try{const v=JSON.parse(localStorage.getItem(key)||'{}');if(v&&typeof v==='object'&&!Array.isArray(v))notes=v;}catch(_){}
  const el=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e;};
  function save(){try{localStorage.setItem(key,JSON.stringify(notes));$('save-status').textContent='검토 메모를 이 브라우저에 저장했습니다. 공식 승인에는 반영되지 않습니다.';}catch(_){$('save-status').textContent='이 브라우저에 저장할 수 없습니다. 메모 내보내기를 사용하세요.';}}
  function render(){
    document.querySelectorAll('audio').forEach(a=>a.pause());const filter=$('filter').value,term=$('search').value.trim();$('list').replaceChildren();
    let entries=filter==='recorded'?report.recordings:report.targets.filter(x=>filter==='all'||filter==='missing'&&!x.recordingAvailable||filter==='names'&&x.groups.includes('자음 이름')||filter==='week'&&x.groups.includes('7일 과정'));
    entries=entries.filter(x=>!term||x.text.includes(term)||(x.labels||[]).some(v=>v.includes(term)));
    $('list').append(el('p',`표시 ${entries.length}개 · 녹음은 한 번에 하나씩 재생하세요.`));
    entries.forEach(item=>{
      const row=el('div');row.className='review-row notranslate';row.translate=false;row.append(el('h3',item.text));
      const source=report.recordings.find(x=>x.text===item.text);row.append(el('p',(item.groups||[]).join(' · ')||(source?'녹음 파일':'녹음 준비 중')));
      if(!source)row.append(el('p','녹음 없음 · 사람 녹음 교체 후보를 선택할 수 있습니다.'));
      if(source){
      const type=el('p',source.kind==='synthetic'?'합성 음성 후보 · 실제 사람의 녹음이 아닙니다.':(source.stage1Candidate||source.stage2Candidate)?'사람의 녹음 · 청취 검수 전 후보입니다.':'사람의 녹음 · 교사 청취 승인 전입니다.');type.className=source.kind==='synthetic'?'held':'small';row.append(type);if(source.stage2Candidate){const check=el('p','연속 녹음에서 순서대로 분리한 임시 대응입니다. 이름과 구간이 맞는지 직접 확인해야 합니다.');check.className='held';row.append(check);}if(source.kind==='synthetic'&&source.alignmentObserved){const ref=el('p','자동 전사 참고: '+source.alignmentObserved+' · 오인식이 있을 수 있으며 실제 발음 판정이 아닙니다.');ref.className='small';row.append(ref);}
      if(source.held){const notice=el('p','일반 학습 화면 재생 보류 · '+(source.holdReason||source.signalWarnings.join(' / ')));notice.className='held';row.append(notice);}
      row.append(el('p',`자동 해독 검사 통과 · 실제 청취 미검증 · ${source.duration}초 · 앞 여백 ${source.leadingSilence}초 · 뒤 여백 ${source.trailingSilence}초`));
      }
      const audio=el('audio');audio.controls=true;audio.preload='none';if(source&&safeSrc(source.src))audio.src=source.src;audio.setAttribute('aria-label',item.text+' 검수용 녹음');row.append(audio);
      const id=source?source.src:JSON.stringify(['missing',item.text]),old=notes[id]||{},label=el('label','내 청취 메모 '),select=el('select');
      for(const [value,text] of [['pending','미검토'],['checked','소리 확인함 · 내 메모'],['rerecord','재녹음 필요'],['uncertain','판단 보류']]){const opt=el('option',text);opt.value=value;select.append(opt);}select.value=old.status||'pending';select.disabled=true;label.append(select);row.append(label);
      const hint=el('p','끝까지 들으면 메모 상태를 선택할 수 있습니다.');hint.className='small';row.append(hint);
      const note=el('textarea');note.placeholder='예: 끝소리가 잘림 / 첫소리에 모음이 덧붙음';note.value=typeof old.note==='string'?old.note:'';note.setAttribute('aria-label',item.text+' 검토 메모');row.append(note);
      audio.onplay=()=>document.querySelectorAll('audio').forEach(a=>{if(a!==audio)a.pause();});
      audio.onended=()=>{select.disabled=false;hint.textContent='재생 완료. 실제 들은 소리를 기준으로 메모하세요. 자동으로 승인되지 않습니다.';};
      audio.onerror=()=>{hint.textContent='파일 재생 실패. 이 항목을 승인하지 말고 기기와 파일을 확인하세요.';select.disabled=true;};
      const update=()=>{notes[id]={text:item.text,status:select.value,note:note.value,updatedAt:new Date().toISOString()};save();};select.onchange=update;note.oninput=update;
      finalReview(row,item,source,audio,select,hint);
      if(source&&source.sourceUrl){const link=el('a',source.kind==='synthetic'?'생성 모델·이용 조건':'원본 출처');link.href=source.sourceUrl;row.append(link);}$('list').append(row);
    });
  }
  $('filter').onchange=render;$('search').oninput=render;
  $('export').onclick=()=>{const blob=new Blob([JSON.stringify({scope:report.scope,officialApproval:false,approvalCountType:'local decisions only',localApprovedCount:Object.values(decisions).filter(x=>x&&x.decision==='approved').length,notes,decisions},null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=el('a');a.href=url;a.download='hangul-listening-notes.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  Promise.all(['./hangul-audio-audit.json?v=20261026-human-only','./hangul-audio-manifest.json'].map(url=>fetch(url).then(r=>{if(!r.ok)throw Error();return r.json();}))).then(([data,currentManifest])=>{if(!state||!Array.isArray(currentManifest.recordings))throw Error();manifest=currentManifest;report={...data,recordings:data.recordings.filter(x=>x.kind==='human'&&!x.retiredSynthetic)};const c=data.counts;$('summary').textContent=(weekScope?`7일 과정 사람 녹음 ${data.week.available}/${data.week.targets}개 · 녹음 필요 ${data.week.missing}개 · 공식 청취 승인과 로컬 결정은 별도입니다. `:'')+`실제 사람 녹음 원칙 · 합성 ${c.excludedSynthetic}개 제외 · 전체 대상 ${c.targets}개 중 사람 녹음 ${c.humanFiles}개 · 일반 화면 재생 ${c.playbackAvailable}개 · 검수 전 보류 ${c.held}개`;$('export').disabled=false;render();countDecisions();}).catch(()=>{$('summary').textContent='검수 자료를 불러오지 못했습니다. 새로고침해 주세요.';});
})();
