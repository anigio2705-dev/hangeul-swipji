/* Exercise the actual board event handler with a minimal DOM and a human-audio inventory. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '..');
const board = fs.readFileSync(path.join(root, 'hangul-board.js'), 'utf8');
const html = fs.readFileSync(path.join(root, 'hangul-basics.html'), 'utf8');

function element(id) {
  return {
    id, children: [], dataset: {}, value: '', textContent: '', classList: { toggle() {} },
    append(...children) { this.children.push(...children); },
    replaceChildren(...children) { this.children = children; },
    setAttribute() {}
  };
}
async function exercise(recorded, held = [], playbackStatus = 'played') {
  const nodes = new Map(), calls = [], statuses = [];
  const get = id => { if (!nodes.has(id)) nodes.set(id, element(id)); return nodes.get(id); };
  const consonants = [
    ['ㄱ', '기역', '가'], ['ㄴ', '니은', '나'], ['ㄷ', '디귿', '다'],
    ['ㄹ', '리을', '라'], ['ㅁ', '미음', '마'], ['ㅂ', '비읍', '바'],
    ['ㅅ', '시옷', '사'], ['ㅇ', '이응', '아'], ['ㅈ', '지읒', '자'],
    ['ㅊ', '치읓', '차'], ['ㅋ', '키읔', '카'], ['ㅌ', '티읕', '타'],
    ['ㅍ', '피읖', '파'], ['ㅎ', '히읗', '하']
  ];
  const H = {
    consonants, vowels: [['ㅏ', '아']], ready: Promise.resolve(),
    el: (tag, cls, text) => { const e = element(tag); e.textContent = text || ''; return e; },
    compose: () => '가', soundButton: () => element('sound'),
    availability: word => ({ state: held.includes(word) ? 'held' : recorded.includes(word) ? 'ready' : 'missing', label: 'test' }),
    refreshBadges() {}, stop() {},
    status: message => statuses.push(message),
    play: async value => { calls.push(value); return { status: playbackStatus }; }
  };
  const document = {
    getElementById: get, createElement: tag => element(tag), querySelectorAll: () => []
  };
  vm.runInNewContext(board, { window: { HSHangul: H }, document }, { filename: 'hangul-board.js' });
  assert.equal(typeof get('play-basic-sequence').onclick, 'function');
  await get('play-basic-sequence').onclick();
  return { calls, statuses };
}
async function main() {
  assert.match(html, /id="play-basic-sequence"/);
  assert.match(html, /hangul-board\.js\?v=20261030-partial-audio/);
  assert.match(html, /hangul-core\.js\?v=20261030-partial-audio/);
  const some = await exercise(['가', '나']);
  assert.equal(some.calls.length, 1);
  assert.deepEqual(Array.from(some.calls[0]), ['가', '나']);
  assert.match(some.statuses.at(-1), /14음절 중 2개.*미재생:/);
  assert.match(some.statuses.at(-1), /누락·검수 보류/);
  const none = await exercise([]);
  assert.equal(none.calls.length, 0);
  assert.match(none.statuses.at(-1), /14음절 중 재생 가능한 사람 녹음이 0개/);
  const held = await exercise(['가', '나'], ['다']);
  assert.deepEqual(Array.from(held.calls[0]), ['가', '나'], 'held recordings must not be played');
  assert.match(held.statuses.at(-1), /미재생:.*다/);
  const error = await exercise(['가'], [], 'error');
  assert.equal(error.statuses.length, 0, 'playback failure must not be overwritten by coverage summary');
  console.log('PASS: board listening button, available-only playback and no-audio fallback');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
