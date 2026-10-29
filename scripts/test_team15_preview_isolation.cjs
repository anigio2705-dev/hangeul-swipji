'use strict';
// Independent Team15 acceptance: original public homepage bytes remain untouched.
// Test-only notice and team12 handoff must be retained on a separate preview page.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const cp = require('node:child_process');
const path = require('node:path');
const root = path.join(__dirname, '..');
const original = cp.execFileSync('git', ['show', '7418e32:index.html'], {cwd: root});
const home = fs.readFileSync(path.join(root, 'index.html'));
const preview = fs.readFileSync(path.join(root, 'index-preview.html'), 'utf8');
assert.deepEqual(home, original, 'protected index.html must match the approved original byte-for-byte');
assert.doesNotMatch(home.toString('utf8'), /hs-issue4-preview-notice|team12_learning_handoff/);
assert.match(preview, /id="hs-issue4-preview-notice"/);
assert.match(preview, /scripts\/team12_learning_handoff\.js/);
assert.match(preview, /실제 결제정보를 입력하지 마세요/);
console.log('PASS Team15 protected homepage exact bytes; preview notice and learning handoff retained separately');
