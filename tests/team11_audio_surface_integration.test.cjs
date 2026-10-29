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
