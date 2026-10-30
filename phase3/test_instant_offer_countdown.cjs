// Node 20: node phase3/test_instant_offer_countdown.cjs
// Exercises the real embedded UI script with a disposable DOM/network; no Jitsi or payment.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
(async () => {
  const html = fs.readFileSync(path.join(__dirname, 'instant-speaking.html'), 'utf8');
  assert.match(html, /id="offerCountdown" role="timer" aria-live="off" hidden/);
  const script = html.match(/<script>([\s\S]*?)<\/script>/);
  assert.ok(script, 'instant matching script must exist');
  const elements = {};
  for (const id of ['loginBox','matching','who','queue','ready','start','stop',
                    'status','notice','video','error','login','email','password','offerCountdown']) {
    elements[id] = { hidden: false, textContent: '', disabled: false, value: '',
                     querySelector() { return null; } };
  }
  let now = 1_000_000, calls = 0, nextId = 1;
  let response = { user: { nickname: 'learner', role: 'learner' }, eligible: true,
                   state: 'offered', partnerName: 'partner', ready: false,
                   expiresAt: now / 1000 + 3, matchId: 'disposable-match' };
  class Clock extends Date { static now() { return now; } }
  const intervals = new Map(), handlers = {};
  const context = {
    document: { getElementById: id => elements[id],
                createElement: tag => ({ tag }) },
    addEventListener: (event, fn) => { handlers[event] = fn; },
    fetch: async () => { calls++; return { ok: true, status: 200, json: async () => response }; },
    setInterval: (fn, ms) => { const id = nextId++; intervals.set(id, { fn, ms }); return id; },
    clearInterval: id => intervals.delete(id),
    setTimeout, clearTimeout, Date: Clock,
    AbortController
  };
  vm.runInNewContext(script[1], context, { filename: 'instant-speaking.html', timeout: 1000 });
  const flush = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
  await flush();
  assert.match(elements.offerCountdown.textContent, /3초/);
  assert.equal(elements.offerCountdown.hidden, false);
  now += 4_000;
  for (const entry of intervals.values()) if (entry.ms === 1000) entry.fn();
  assert.match(elements.offerCountdown.textContent, /시간이 지났습니다/);
  assert.equal(calls, 1, 'countdown must not flood matching API');
  response = { user: { nickname: 'learner', role: 'learner' }, eligible: true, state: 'idle' };
  handlers.pageshow();
  await flush();
  assert.equal(elements.offerCountdown.hidden, true, 'expired offer must disappear after server idle');
  assert.equal(elements.offerCountdown.textContent, '');
  handlers.pagehide();
  assert.equal(intervals.size, 0, 'navigation must release countdown and polling timers');
  assert.equal(calls, 2);
  console.log('PASS: live offer countdown, expiry, server refresh, and cleanup');
})().catch(err => { console.error(err); process.exitCode = 1; });
