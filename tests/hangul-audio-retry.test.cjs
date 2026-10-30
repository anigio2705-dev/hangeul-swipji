'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'hangul-core.js'), 'utf8');
const human = (src, extra = {}) => ({
  kind: 'human', src, sourceUrl: 'https://example.org/recording',
  author: 'Recorded speaker', license: 'CC BY 4.0', ...extra,
});

function harness(fetchImpl) {
  const played = [];
  const statuses = [];
  const context = {
    fetch: fetchImpl, setTimeout, clearTimeout, queueMicrotask,
    Event: class { constructor(type) { this.type = type; } },
    Audio: class {
      constructor(src) { this.src = src; played.push(src); }
      play() { queueMicrotask(() => this.onended?.()); return Promise.resolve(); }
      pause() {}
    },
    document: {
      querySelectorAll() { return [{set textContent(value) { statuses.push(value); }}]; },
      querySelector() { return null; },
      dispatchEvent() {}, addEventListener() {},
    },
    window: {speechSynthesis: {cancel() {}}, addEventListener() {}},
  };
  vm.runInNewContext(source, context, {filename: 'hangul-core.js'});
  return {api: context.window.HSHangul, played, statuses};
}

test('a failed initial manifest fetch retries on tap and plays verified human audio', async () => {
  let calls = 0;
  const {api, played} = harness(async (_url, options) => {
    calls++;
    assert.equal(options.cache, 'no-store');
    if (calls === 1) throw Error('temporary network outage');
    return {ok: true, json: async () => ({
      recordings: {'가': human('./assets/hangul-audio/ga.mp3')},
    })};
  });
  await api.ready;
  assert.equal((await api.play('가')).status, 'played');
  assert.equal(calls, 2);
  assert.deepEqual(played, ['./assets/hangul-audio/ga.mp3']);
});

test('held, missing, and synthetic entries cannot be played as human recordings', async () => {
  const {api, played} = harness(async () => ({ok: true, json: async () => ({
    recordings: {
      '가': human('./assets/hangul-audio/ga.mp3'),
      '나': human('./assets/hangul-audio/na.mp3', {disabled: true, holdReason: 'review pending'}),
      '다': {kind: 'synthetic', src: './assets/hangul-audio/da.mp3'},
    },
  })}));
  await api.ready;
  assert.equal((await api.play('나')).status, 'held');
  assert.equal((await api.play('다')).status, 'missing');
  assert.equal((await api.play('가')).status, 'played');
  assert.deepEqual(played, ['./assets/hangul-audio/ga.mp3']);
});

test('persistent network failures remain fail-closed but can retry again', async () => {
  let calls = 0;
  const {api, played} = harness(async () => { calls++; throw Error('offline'); });
  await api.ready;
  assert.equal((await api.play('가')).status, 'manifest-error');
  assert.equal((await api.play('가')).status, 'manifest-error');
  assert.equal(calls, 3);
  assert.equal(played.length, 0);
});

test('malformed manifest array is rejected and a later valid response recovers', async () => {
  let calls = 0;
  const {api} = harness(async () => {
    calls++;
    return {ok: true, json: async () => ({
      recordings: calls === 1 ? [] : {'가': human('./assets/hangul-audio/ga.mp3')},
    })};
  });
  await api.ready;
  assert.equal((await api.play('가')).status, 'played');
  assert.equal(calls, 2);
});
