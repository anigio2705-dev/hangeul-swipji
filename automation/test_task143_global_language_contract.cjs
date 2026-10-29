'use strict';
// #143: independent, network-free regression for the legacy website-language widget.
// This does not certify the actual quality or completeness of machine translation.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '..', 'global-language.js'), 'utf8');
const approved = ['ko', 'en', 'ja', 'es', 'ru', 'zh-CN', 'mn', 'vi'];
const list = source.match(/const langs=(\[[^;\n]+\]);/);
assert.ok(list, 'legacy widget must expose an explicit supported-language list');
const codes = [...list[1].matchAll(/\['([^']+)','[^']+'\]/g)].map(x => x[1]);
assert.deepEqual(codes, approved, 'unverified languages must remain hidden');
assert.equal(new Set(codes).size, approved.length, 'no duplicate language codes');

const match = source.match(/result\.split\((\/[^;\n]+\/)\)/);
assert.ok(match, 'batch translation separator must be explicit');
const separator = vm.runInNewContext(match[1]);
assert.deepEqual('첫째 [~] 둘째 [~] 셋째'.split(separator),
                 ['첫째', '둘째', '셋째'], 'batch results must split into original items');
assert.deepEqual('first[~]second'.split(separator), ['first', 'second']);
assert.deepEqual('ordinary [not a separator] text'.split(separator),
                 ['ordinary [not a separator] text']);
console.log('Task #143 PASS: eight UI languages, no duplicate, batched delimiter and negative fixture');
