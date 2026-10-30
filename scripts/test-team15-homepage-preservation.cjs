'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const cp=require('node:child_process');
const path=require('node:path');
const {validateHomepage}=require('./homepage-source-contract.cjs');
const root=path.resolve(__dirname,'..');
const original=cp.execFileSync('git',['show','46745d28b17554f7d0f67e3e5515778b7ccb35e3:index.html'],{cwd:root,encoding:'utf8'});
const teaching=cp.execFileSync('git',['show','7418e32:index.html'],{cwd:root,encoding:'utf8'});
const current=fs.readFileSync(path.join(root,'index.html'),'utf8');
assert.deepEqual(validateHomepage(original,original),{ok:true,variant:'original'});
assert.equal(validateHomepage(teaching,original).ok,true);
assert.equal(validateHomepage(current,original).ok,true,'Exact current staging additions must be reversible');
assert.equal(validateHomepage(current,original).variant,'staging-handoff-and-layout');
for(const [label,mutant] of [
 ['injected script',current.replace('</body>','<script>alert(1)</script></body>')],
 ['altered layout',current.replace('min-height:640px','min-height:641px')],
 ['missing handoff',current.replace('data-team12-handoff','data-team12-broken')],
 ['duplicated handoff',current.replace('</body>','<div class="shell" data-team12-handoff></div><script src="./scripts/team12_learning_handoff.js" defer></script></body>')],
 ['tampered teaching',current.replace('강사 수업 · 테스트','강사 수업 · 임의변경')]
]){
 assert.notEqual(mutant,current,label+' fixture did not mutate');
 assert.equal(validateHomepage(mutant,original).ok,false,label+' must fail closed');
}
console.log('Team15 homepage source preservation: original + exact teaching + exact staging PASS; 5 mutations rejected.');
