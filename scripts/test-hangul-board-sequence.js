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
async function exercise(recorded, opts = {}) {
  const nodes = new Map(), calls = [], statuses = [];
  let manifestFailed = !!opts.manifestFailed, retries = 0;
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
    availability: word => ({ state: manifestFailed ? 'unavailable' : recorded.includes(word) ? 'ready' : 'missing', label: 'test' }),
    retryManifest: async () => { retries++; if (opts.recoverTo) { recorded = opts.recoverTo; manifestFailed = false; } },
    refreshBadges() {}, stop() {},
    status: message => statuses.push(message),
    play: async value => { calls.push(value); return { status: 'played' }; }
  };
  const document = {
    getElementById: get, createElement: tag => element(tag), querySelectorAll: () => []
  };
  vm.runInNewContext(board, { window: { HSHangul: H }, document }, { filename: 'hangul-board.js' });
  assert.equal(typeof get('play-basic-sequence').onclick, 'function');
  await get('play-basic-sequence').onclick();
  return { calls, statuses, retries };
}
async function main() {
  assert.match(html, /id="play-basic-sequence"/);
  assert.match(html, /hangul-board\.js\?v=20261030-partial-audio/);
  assert.match(html, /hangul-core\.js\?v=20261030-partial-audio/);
  const some = await exercise(['가', '나']);
  assert.equal(some.calls.length, 1);
  assert.deepEqual(Array.from(some.calls[0]), ['가', '나']);
  assert.match(some.statuses.at(-1), /2\/14개 재생/);
  assert.match(some.statuses.at(-1), /다/);
  const none = await exercise([]);
  assert.equal(none.calls.length, 0);
  assert.match(none.statuses.at(-1), /재생 가능한 사람 녹음이 없습니다/);
  const recovered = await exercise([], { manifestFailed: true, recoverTo: ['가', '나'] });
  assert.equal(recovered.retries, 1, 'failed manifest must retry once on sequence click');
  assert.deepEqual(Array.from(recovered.calls[0]), ['가', '나']);
  assert.match(recovered.statuses.at(-1), /2\/14개 재생/);
  const stillOffline = await exercise([], { manifestFailed: true });
  assert.equal(stillOffline.retries, 1);
  assert.equal(stillOffline.calls.length, 0);
  assert.match(stillOffline.statuses.at(-1), /음성 목록 연결 실패/);
  console.log('PASS: board listening button, available-only playback and no-audio fallback');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
