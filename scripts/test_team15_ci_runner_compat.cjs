'use strict';
// Independent Team15 guard: Playwright 1.51.1 cannot install Chromium on
// ubuntu26.04. The runner previously drifted there via ubuntu-latest.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const workflow = fs.readFileSync(path.join(__dirname, '../.github/workflows/integration-validation.yml'), 'utf8');
function validateWorkflow(source) {
  const matches = [...source.matchAll(/^\s*runs-on:\s*([^\s#]+)/gm)];
  assert.equal(matches.length, 1, 'integration validation must have exactly one explicit runner');
  assert.equal(matches[0][1], 'ubuntu-24.04', 'pin supported Ubuntu for Playwright Chromium');
  assert.match(source, /playwright install --with-deps chromium/, 'keep real Chromium dependency installation');
  assert.match(source, /node phase3\/browser-test\.cjs/, 'keep real browser regression');
}
validateWorkflow(workflow);
for (const unsupported of ['ubuntu-latest', 'ubuntu-26.04']) {
  assert.throws(() => validateWorkflow(workflow.replace(/runs-on:\s*ubuntu-24\.04/, 'runs-on: ' + unsupported)), /pin supported Ubuntu/);
}
assert.throws(() => validateWorkflow(workflow.replace('playwright install --with-deps chromium', 'echo skip-browser')), /Chromium dependency/);
console.log('PASS Team15 independent Playwright runner guard: supported runner and three rejected regressions');
