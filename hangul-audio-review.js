(() => {
  'use strict';
  const $=id=>document.getElementById(id),key='hs-audio-review-v1';let report,notes={};
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
      if(source.held){const notice=el('p','일반 학습 화면 재생 보류 · '+source.signalWarnings.join(' / '));notice.className='held';row.append(notice);}
      row.append(el('p',`파일 검사: 재생 가능 · ${source.duration}초 · 앞 여백 ${source.leadingSilence}초 · 뒤 여백 ${source.trailingSilence}초`));
      const audio=el('audio');audio.controls=true;audio.preload='none';audio.src=source.src;audio.setAttribute('aria-label',item.text+' 검수용 녹음');row.append(audio);
      const id=source.src,old=notes[id]||{},label=el('label','내 청취 메모 '),select=el('select');
      for(const [value,text] of [['pending','미검토'],['checked','소리 확인함 · 내 메모'],['rerecord','재녹음 필요'],['uncertain','판단 보류']]){const opt=el('option',text);opt.value=value;select.append(opt);}select.value=old.status||'pending';select.disabled=true;label.append(select);row.append(label);
      const hint=el('p','끝까지 들으면 메모 상태를 선택할 수 있습니다.');hint.className='small';row.append(hint);
      const note=el('textarea');note.placeholder='예: 끝소리가 잘림 / 첫소리에 모음이 덧붙음';note.value=typeof old.note==='string'?old.note:'';note.setAttribute('aria-label',item.text+' 검토 메모');row.append(note);
      audio.onplay=()=>document.querySelectorAll('audio').forEach(a=>{if(a!==audio)a.pause();});
      audio.onended=()=>{select.disabled=false;hint.textContent='재생 완료. 실제 들은 소리를 기준으로 메모하세요. 자동으로 승인되지 않습니다.';};
      audio.onerror=()=>{hint.textContent='파일 재생 실패. 이 항목을 승인하지 말고 기기와 파일을 확인하세요.';select.disabled=true;};
      const update=()=>{notes[id]={text:item.text,status:select.value,note:note.value,updatedAt:new Date().toISOString()};save();};select.onchange=update;note.oninput=update;
      const link=el('a','원본 출처');link.href=source.sourceUrl;row.append(link);$('list').append(row);
    });
  }
  $('filter').onchange=render;$('search').oninput=render;
  $('export').onclick=()=>{const blob=new Blob([JSON.stringify({scope:report.scope,officialApproval:false,notes},null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=el('a');a.href=url;a.download='hangul-listening-notes.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  fetch('./hangul-audio-audit.json?v=20261026-audio-audit').then(r=>{if(!r.ok)throw Error();return r.json();}).then(data=>{report=data;const c=data.counts;$('summary').textContent=`전체 ${c.targets}개 · 녹음 확보 ${c.available}개 · 녹음 없음 ${c.missing}개 · 재생 가능 ${c.playbackAvailable}개 · 보류 ${c.held}개 · 공식 청취 승인 ${c.listeningApproved}개`;$('export').disabled=false;render();}).catch(()=>{$('summary').textContent='검수 자료를 불러오지 못했습니다. 새로고침해 주세요.';});
})();
