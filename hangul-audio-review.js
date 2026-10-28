(() => {
  'use strict';
  const $=id=>document.getElementById(id),key='hs-audio-review-v1',weekScope=new URLSearchParams(location.search).get('scope')==='week';if(weekScope)$('filter').value='week';let report,manifest,notes={};
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
      if(!source){row.append(el('p','녹음 없음 · 정확한 소리로 녹음한 뒤 검수가 필요합니다.'));$('list').append(row);return;}
      const type=el('p',source.kind==='synthetic'?'합성 음성 후보 · 실제 사람의 녹음이 아닙니다.':(source.stage1Candidate||source.stage2Candidate)?'사람의 녹음 · 청취 검수 전 후보입니다.':'사람의 녹음 · 교사 청취 승인 전입니다.');type.className=source.kind==='synthetic'?'held':'small';row.append(type);if(source.stage2Candidate){const check=el('p','연속 녹음에서 순서대로 분리한 임시 대응입니다. 이름과 구간이 맞는지 직접 확인해야 합니다.');check.className='held';row.append(check);}if(source.kind==='synthetic'&&source.alignmentObserved){const ref=el('p','자동 전사 참고: '+source.alignmentObserved+' · 오인식이 있을 수 있으며 실제 발음 판정이 아닙니다.');ref.className='small';row.append(ref);}
      if(source.held){const notice=el('p','일반 학습 화면 재생 보류 · '+(source.holdReason||source.signalWarnings.join(' / ')));notice.className='held';row.append(notice);}
      row.append(el('p',`자동 해독 검사 통과 · 실제 청취 미검증 · ${source.duration}초 · 앞 여백 ${source.leadingSilence}초 · 뒤 여백 ${source.trailingSilence}초`));
      const digest=manifest.recordings[item.text].sha256;
      const audio=el('audio');audio.controls=true;audio.preload='none';const audioUrl=new URL(source.src,location.href);audioUrl.searchParams.set('v',digest.slice(0,16));audio.src=audioUrl.href;audio.setAttribute('aria-label',item.text+' 검수용 녹음');row.append(audio);
      // Notes are bound to the exact audio bytes, not just a reusable filename.
      const id=source.src+'#'+digest,old=notes[id]||{},label=el('label','내 청취 메모 '),select=el('select');
      for(const [value,text] of [['pending','미검토'],['checked','소리 확인함 · 내 메모'],['rerecord','재녹음 필요'],['uncertain','판단 보류']]){const opt=el('option',text);opt.value=value;select.append(opt);}select.value=old.status||'pending';select.disabled=true;label.append(select);row.append(label);
      const hint=el('p','끝까지 들으면 메모 상태를 선택할 수 있습니다.');hint.className='small';row.append(hint);
      const note=el('textarea');note.placeholder='예: 끝소리가 잘림 / 첫소리에 모음이 덧붙음';note.value=typeof old.note==='string'?old.note:'';note.setAttribute('aria-label',item.text+' 검토 메모');row.append(note);
      audio.onplay=()=>document.querySelectorAll('audio').forEach(a=>{if(a!==audio)a.pause();});
      audio.onended=()=>{select.disabled=false;hint.textContent='재생 완료. 실제 들은 소리를 기준으로 메모하세요. 자동으로 승인되지 않습니다.';};
      audio.onerror=()=>{hint.textContent='파일 재생 실패. 이 항목을 승인하지 말고 기기와 파일을 확인하세요.';select.disabled=true;};
      const update=()=>{notes[id]={text:item.text,status:select.value,note:note.value,updatedAt:new Date().toISOString()};save();};select.onchange=update;note.oninput=update;
      const link=el('a',source.kind==='synthetic'?'생성 모델·이용 조건':'원본 출처');link.href=source.sourceUrl;row.append(link);$('list').append(row);
    });
  }
  $('filter').onchange=render;$('search').oninput=render;
  $('export').onclick=()=>{const blob=new Blob([JSON.stringify({scope:report.scope,officialApproval:false,notes},null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=el('a');a.href=url;a.download='hangul-listening-notes.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  Promise.all(['./hangul-audio-audit.json?v=20261026-human-only','./hangul-audio-manifest.json?v=20261029-review-integrity'].map(url=>fetch(url,{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('자료 연결 오류');return r.json();})))
    .then(([data,inventory])=>{
      if(!data||!Array.isArray(data.recordings)||!inventory||!inventory.recordings||
         !data.recordings.every(item=>{const audio=inventory.recordings[item.text];return audio&&audio.kind==='human'&&audio.src===item.src&&/^[a-f0-9]{64}$/i.test(audio.sha256||'');}))
        throw Error('검수 자료와 현재 음원 목록이 일치하지 않습니다.');
      report=data;manifest=inventory;const c=data.counts;$('summary').textContent=(weekScope?`7일 과정 사람 녹음 ${data.week.available}/${data.week.targets}개 · 녹음 필요 ${data.week.missing}개 · 청취 승인 0개. `:'')+`실제 사람 녹음 원칙 · 합성 ${c.excludedSynthetic}개 제외 · 전체 대상 ${c.targets}개 중 사람 녹음 ${c.humanFiles}개 · 일반 화면 재생 ${c.playbackAvailable}개 · 검수 전 보류 ${c.held}개`;$('export').disabled=false;render();}).catch(error=>{$('summary').textContent=(error&&error.message)||'검수 자료를 불러오지 못했습니다. 새로고침해 주세요.';$('export').disabled=true;});
})();
