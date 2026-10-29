/* Regression for mixed recorded/missing Hangul audio; no network or browser dependencies. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'hangul-core.js'), 'utf8');
const src = word => './assets/hangul-audio/' + word + '.mp3';
const recording = word => ({
  kind: 'human', src: src(word), sourceUrl: 'https://example.org/source',
  author: 'test', license: 'CC0'
});

async function harness(autoEnd = true) {
  const played = [], messages = [];
  const recordings = {
    '가': recording('ga'),
    '나': recording('na'),
    '차': { ...recording('cha'), disabled: true, holdReason: 'review pending' }
  };
  class FakeAudio {
    constructor(file) { this.src = file; }
    play() {
      played.push(this.src);
      if (autoEnd) Promise.resolve().then(() => { if (this.onended) this.onended(); });
      return Promise.resolve();
    }
    pause() {}
  }
  const statusNode = { set textContent(value) { messages.push(value); } };
  const document = {
    addEventListener() {}, dispatchEvent() {},
    querySelectorAll() { return [statusNode]; }, querySelector() { return null; }
  };
  const window = { addEventListener() {} };
  vm.runInNewContext(source, {
    window, document, Audio: FakeAudio, Event: class Event {},
    fetch: async () => ({ ok: true, json: async () => ({ recordings }) })
  }, { filename: 'hangul-core.js' });
  await window.HSHangul.ready;
  return { core: window.HSHangul, played, messages };
}

async function main() {
  {
    const h = await harness();
    const result = await h.core.play(['가', '미', '나']);
    assert.equal(result.status, 'partial', 'recorded syllables must play despite missing neighbor');
    assert.deepEqual(Array.from(result.words), ['가', '나']);
    assert.deepEqual(Array.from(result.missing), ['미']);
    assert.deepEqual(h.played, [src('ga'), src('na')]);
    assert.match(h.messages.at(-1), /일부만 재생.*미/);
  }
  {
    const h = await harness();
    const result = await h.core.play(['미', '리']);
    assert.equal(result.status, 'missing', 'no recordings must not claim playback');
    assert.deepEqual(h.played, []);
  }
  {
    const h = await harness();
    const result = await h.core.play(['가', '차']);
    assert.equal(result.status, 'held', 'review-held recordings must never be bypassed');
    assert.deepEqual(h.played, []);
  }
  {
    const h = await harness();
    const result = await h.core.play(['가', '나']);
    assert.equal(result.status, 'played', 'fully recorded sequences retain existing behavior');
    assert.deepEqual(h.played, [src('ga'), src('na')]);
  }
  {
    const h = await harness();
    assert.equal((await h.core.play(['미'])).status, 'missing');
    assert.equal((await h.core.play([''])).status, 'invalid');
    assert.deepEqual(h.played, []);
  }
  {
    const h = await harness(false);
    const pending = h.core.play(['가', '나']);
    for (let i = 0; i < 20 && h.played.length === 0; i++) await Promise.resolve();
    assert.equal(h.played.length, 1, 'first recording must start before cancellation');
    h.core.stop();
    const result = await pending;
    assert.equal(result.status, 'cancelled');
    assert.equal(h.played.length, 1, 'stop must prevent second recording');
  }
  console.log('PASS: six Hangul playback regressions (mixed, missing, held, full, invalid, stop)');
}

main().catch(error => { console.error(error); process.exitCode = 1; });
