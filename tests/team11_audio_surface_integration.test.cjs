/* Integration gate: both teaching surfaces expose default-off TTS and wire to the same audio engine. */
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.join(__dirname,'..');
const read=file=>fs.readFileSync(path.join(root,file),'utf8');
for(const [page,script] of [['hangul-basics.html','hangul-board.js'],['hangul-week.html','hangul-week.js']]){
  test(page+' audio consent is visible, opt-in, and wired',()=>{
    const html=read(page),js=read(script);
    assert.match(html,/<input[^>]*type="checkbox"[^>]*id="tts-opt-in"/);
    assert.doesNotMatch(html,/<input[^>]*id="tts-opt-in"[^>]*checked(?:\s|=|>)/);
    assert.match(html,/hangul-core\.js\?v=20261030/);
    assert.match(js,/setSyntheticEnabled\(/);
    assert.match(js,/tts-opt-in/);
    assert.match(js,/refreshBadges\(/);
  });
}
test('shared engine is human-first and synthetic speech defaults off',()=>{
  const core=read('hangul-core.js');
  assert.match(core,/let syntheticEnabled=false/);
  assert.match(core,/if\(records\[word\]\)\{await recording\(word,token\);continue\}/);
  assert.match(core,/if\(!syntheticEnabled&&missing\.length\)/);
  assert.match(core,/utterance\.lang='ko-KR'/);
});


test('mobile audio resume fix is cache-busted on both learner surfaces',()=>{
  for(const page of ['hangul-basics.html','hangul-week.html']){
    assert.match(read(page),/hangul-core\\.js\\?v=20261030-team11-foreground3/,
      page+' must not serve an older cached core after mobile background resume');
  }
});
test('seven-day learner UI does not falsely claim pronunciation was reviewed',()=>{
  const page=read('hangul-week.html');
  assert.doesNotMatch(page,/♪ 표시는 검수된 사람 녹음입니다/);
  assert.match(page,/청취 검수 전/);
});
