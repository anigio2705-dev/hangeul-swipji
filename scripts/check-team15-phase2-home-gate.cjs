// Team15-derived negative regression for the independent Phase2 homepage gate.
// Runs only on disposable CI checkouts; always restores the original source.
'use strict';
const fs=require('node:fs');
const path=require('node:path');
const cp=require('node:child_process');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const homepage=path.join(root,'index.html');
const original=fs.readFileSync(homepage);
const run=()=>cp.spawnSync(process.execPath,['scripts/audit-phase2-content.cjs'],{cwd:root,encoding:'utf8',timeout:45000});
const baseline=run();
assert.equal(baseline.status,0,'approved homepage must pass: '+(baseline.stderr||baseline.stdout||'').slice(-900));
for(const extra of ['\n<!-- unauthorized homepage edit -->\n','min-height:640px']){
 try{
  fs.writeFileSync(homepage,Buffer.concat([original,Buffer.from(extra)]));
  const result=run();
  assert.notEqual(result.status,0,'homepage audit must reject injected change');
  assert.match(result.stdout||'',/Homepage changed beyond exact approved staging UI deltas/);
 }finally{fs.writeFileSync(homepage,original);}
}
const restored=run();
assert.equal(restored.status,0,'restored approved homepage must pass');
console.log('PASS: Phase2 homepage strict baseline, arbitrary tamper, duplicate UI delta, and restore');
