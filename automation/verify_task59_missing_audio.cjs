'use strict';
// Execute the real board script in a tiny DOM simulation. No network, TTS or audio files.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'hangul-board.js'), 'utf8');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'hangul-audio-manifest.json'), 'utf8'));
assert.equal(manifest.recordings['모'], undefined, 'The missing standalone 모 audio must not be falsely marked as available');
const nodes = new Map(), buttons = [], played = [], statuses = [];
function el(tag = 'div', cls = '', text = '') {
  const e = {
    tagName: tag, className: cls, textContent: text, children: [], dataset: {},
    classList: { toggle() {} }, disabled: false,
    append(...items) { this.children.push(...items); },
    replaceChildren(...items) { this.children = items; },
    setAttribute(key, value) { this[key] = value; }
  };
  return e;
}
const document = {
  getElementById(id) { if (!nodes.has(id)) nodes.set(id, el()); return nodes.get(id); },
  createElement(tag) { return el(tag); },
  querySelectorAll() { return buttons; }
};
const records = { '가': { src: './assets/hangul-audio/ac00-r2.mp3' } };
const H = {
  consonants: [['ㄱ', '기역', '가'], ['ㅁ', '미음', '마']],
  vowels: [['ㅏ', '아'], ['ㅗ', '오']], records,
  compose(c, v) { return c === 'ㅁ' && v === 'ㅗ' ? '모' : '가'; },
  el, soundButton(word) { const b = el('button'); b.dataset.sound = word; buttons.push(b); return b; },
  play(word) { played.push(word); }, stop() {}, status(message) { statuses.push(message); },
  ready: Promise.resolve(), refreshBadges() {}
};
vm.runInNewContext(source, { window: { HSHangul: H }, document }, { filename: 'hangul-board.js' });
(async () => {
  await H.ready;
  await new Promise(resolve => setImmediate(resolve));
  const repeat = document.getElementById('repeat-selected');
  assert.equal(repeat.disabled, false, 'Known recorded 가 should remain playable');
  const mo = buttons.find(b => b.dataset.sound === '모');
  assert.ok(mo, '모 must exist on the composed board');
  mo.onclick();
  assert.equal(document.getElementById('selected-syllable').textContent, '모');
  assert.equal(repeat.disabled, true, 'Missing 모 must not show a usable repeat-audio control');
  assert.match(document.getElementById('selected-help').textContent, /모.*녹음.*재생할 수 없습니다/);
  assert.match(statuses.at(-1), /모.*미확보/);
  assert.equal(played.length, 0, 'Missing 모 must not invoke a fake recording');
  repeat.onclick();
  assert.equal(played.length, 0, 'Repeat must not play another syllable for missing 모');
  const ga = buttons.find(b => b.dataset.sound === '가');
  ga.onclick();
  assert.equal(repeat.disabled, false, 'Known 가 must still be playable');
  assert.deepEqual(played, ['가']);
  repeat.onclick();
  assert.deepEqual(played, ['가', '가'], 'Repeat of recorded 가 must still work');
  // Once an independently reviewed human recording is installed, the same board works.
  records['모'] = { src: './assets/hangul-audio/baa8-reviewed.mp3' };
  mo.onclick();
  assert.equal(repeat.disabled, false);
  assert.deepEqual(played, ['가', '가', '모']);
  console.log('PASS: missing 모 is explicitly unavailable; recorded 가 and later reviewed 모 play normally');
})().catch(error => { console.error(error); process.exitCode = 1; });
