(() => {
  'use strict';
  const H=window.HSHangul,$=id=>document.getElementById(id);let selected='가';
  function syncSelectedAudioState(){
    const recorded=Object.prototype.hasOwnProperty.call(H.records,selected);
    const repeat=$('repeat-selected');
    repeat.disabled=!recorded;
    repeat.setAttribute('aria-label',recorded?selected+' 사람 녹음 다시 듣기':selected+' 사람 녹음 미확보');
    $('selected-help').textContent=recorded
      ? '실제 사람 녹음이 있습니다. 청취 정확성은 아직 검수 전입니다.'
      : selected+' · 실제 사람 녹음이 없어 재생할 수 없습니다. 선생님과 함께 읽어 주세요.';
    return recorded;
  }
  function select(c,v,play=true){
    selected=H.compose(c,v);$('selected-syllable').textContent=selected;
    $('selected-formula').textContent=c+' + '+v+' = '+selected;
    document.querySelectorAll('.board [data-sound]').forEach(b=>b.classList.toggle('focus',b.dataset.sound===selected));
    const recorded=syncSelectedAudioState();
    if(play){
      if(recorded)H.play(selected);
      else H.status(selected+' · 사람 녹음 미확보/재생 불가. 녹음 준비 중이거나 음원 목록을 불러오지 못했습니다.');
    }
  }
  for(const [c,name,word] of H.consonants){
    const b=H.soundButton(name);b.replaceChildren(H.el('b','',c),H.el('small','',name));
    b.onclick=()=>{H.status(c+'의 이름은 '+name+'입니다. 음절 소리 '+word+'는 글자판에서 누르세요.');H.play(name)};$('consonants').append(b);
  }
  for(const [v,word] of H.vowels){const b=H.soundButton(word);b.replaceChildren(H.el('b','',v),H.el('small','',word));$('vowels').append(b)}
  function board(host,vowels){
    const table=H.el('table','board notranslate');table.translate=false;
    const caption=H.el('caption','small',vowels.map(v=>v[0]).join(' · ')+' 조합');table.append(caption);
    const thead=document.createElement('thead'),tr=document.createElement('tr');
    const corner=H.el('th','','자음');corner.scope='col';tr.append(corner);
    for(const [v,word] of vowels){const th=H.el('th','',v);th.scope='col';th.append(H.el('small','',word));tr.append(th)}
    thead.append(tr);table.append(thead);const tbody=document.createElement('tbody');
    H.consonants.forEach(([c,name],i)=>{
      const row=H.el('tr',i>=14?'tense':'');const th=H.el('th','',c);th.scope='row';th.append(H.el('small','',name));row.append(th);
      for(const [v] of vowels){const td=document.createElement('td'),word=H.compose(c,v),b=H.soundButton(word);b.onclick=()=>select(c,v);td.append(b);row.append(td)}
      tbody.append(row);
    });table.append(tbody);$(host).append(table);
  }
  board('basic-board',H.vowels.slice(0,10));board('extended-board',H.vowels.slice(10));
  for(const [c,name] of H.consonants){const o=H.el('option','',c+' '+name);o.value=c;$('builder-c').append(o)}
  for(const [v,word] of H.vowels){const o=H.el('option','',v+' '+word);o.value=v;$('builder-v').append(o)}
  $('builder-play').onclick=()=>select($('builder-c').value,$('builder-v').value);
  for(const word of ['국','산','옷','달','밤','밥','강'])$('finals').append(H.soundButton(word));
  for(const [, ,word] of H.consonants.slice(0,14))$('practice').append(H.soundButton(word));
  $('repeat-selected').onclick=()=>{if(syncSelectedAudioState())H.play(selected)};
  $('stop-audio').onclick=()=>{H.stop();H.status('재생을 멈췄습니다.')};
  H.ready.then(()=>{H.refreshBadges();syncSelectedAudioState()});select('ㄱ','ㅏ',false);
})();
