'use strict';
// Independent Team15 guard: Playwright 1.51.1 cannot install Chromium on
// ubuntu26.04. The runner previously drifted there via ubuntu-latest.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const workflow = fs.readFileSync(path.join(__dirname, '../.github/workflows/integration-validation.yml'), 'utf8');
function runner(source) {
  const matches = [...source.matchAll(/^\s*runs-on:\s*([^\s#]+)/gm)];
  assert.equal(matches.length, 1, 'integration validation must have exactly one explicit runner');
  return matches[0][1];
}
assert.equal(runner(workflow), 'ubuntu-24.04', 'pin supported Ubuntu for Playwright Chromium');
assert.match(workflow, /playwright install --with-deps chromium/, 'keep real Chromium dependency installation');
assert.match(workflow, /node phase3\/browser-test\.cjs/, 'keep real browser regression');
for (const unsupported of ['ubuntu-latest', 'ubuntu-26.04']) {
  assert.notEqual(runner('jobs:\n  validate:\n    runs-on: ' + unsupported), 'ubuntu-24.04');
}
console.log('PASS Team15 independent Playwright runner compatibility guard (including negative cases)');
