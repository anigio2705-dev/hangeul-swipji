# Team15 independent CI recovery — 2026-10-28

## Observed failure
Original GitHub Actions run: https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40609708032
Job 122557981772: verify = failure. Source gate success; Team11 **21/21 PASS** (actual log 'Ran 21 tests ... OK'); Team12 inventory failed SyntaxError unexpected character after line continuation character, line near `probe.stderr[:300]`. Team13, Team14 and integration were skipped because of sequential steps.

## Independent team evidence and pinned SHA
- Integration baseline: 2ca95fa1aa8206ec8763443d8256ab54ac789017.
- Team11: 96672116b0c87e34478233d1cf08028413515ff8; actual 21 PASS, 0 fail, from run 40609708032.
- Team12: f14b3df68224b8508d0c4fe6d7e8ba84277cd6a6; newer source no longer shows the malformed line observed in old run; independent py_compile and 399-inventory CI result PENDING.
- Team13: 5c464829dd93e70a8af534ea5e1d0d9ce9bd92f0; workflow uses fetch-depth:0 to retrieve original commit 7418e32. Previous run https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40609599704 had Python FAIL, browser SUCCESS. New SHA Python/browser independently PENDING.
- Team14: e4d912c0752aa1bda1e67831a20e4e5e310be9f5; 14 expected cases, independent run PENDING.
- Team15 QA workflow source changed in 07a31ebd97918f82a1aed0902a197df1ff5311ff.

## Isolation and permissions
Updated .github/workflows/team15-independent-regression.yml to seven independent jobs: source gate, Team11 contract, Team12 audio, Team13 Python, Team13 browser, Team14 monthly, integration baseline. Each job checks out immutable SHA. No job needs another job; a failed job will not skip others. permissions: contents:read only. No payment, production DB, merge or deploy.
Team12: compile first, ffmpeg inventory, artifact retained.
Team13: full Git history, original content commit check, Python log artifact; separate Chromium browser test with npm ci.
Team14: real checked-out monthly tests.
Integration: full history for original content regression.
Workflow push should trigger GitHub Actions, but at report-writing time NEW run URL, job exit codes, pass/fail counts and results have NOT been independently obtained. Do not infer PASS from a commit.

## Remaining risks
Audio file decode/human approval and live playback; Jitsi provider-level room access and actual two-device audio/video; multi-role and scoped approval migration; persistent booking/currency/transaction reconciliation and refund reversal; untested public server and devices. No approval to integrate.
