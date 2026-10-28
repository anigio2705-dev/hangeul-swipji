# Team15 second-pass refreshed audit — 2026-10-28

## Verified heads (GitHub API)
- integration/phase2-phase3-20261027: 2ca95fa1aa8206ec8763443d8256ab54ac789017
- team11/common-foundation-20261028: 96672116b0c87e34478233d1cf08028413515ff8
- team12/education-audit-20261028: 227e68e4573baf130e7e3a68060e58504aeb5571
- team13/platform-bfcache-reconnect-20261028: 234f975c9dd172b124ab3601e6ac317ca7c54bf4
- team14/business-systems-audit-20261028: e4d912c0752aa1bda1e67831a20e4e5e310be9f5
- team15 prior head: 278a8a0c0edf1035bc25505feb018cea2666264a

## Comparison
11-14 share integration as merge base; their extra changes are 14, 6, 6, 7 commits respectively, and files added/changed since integration have no same-path overlap in GitHub compare. This is not a proof of runtime compatibility.
Team15 was created from main, 29 commits behind integration; do not force rebase. A new integration-based review branch plus selective application of Team15-only QA changes is safer.

## New automated checks
- .github/workflows/team15-independent-regression.yml checks out all five source refs separately and runs Python unittest and Team12 inventory.
- scripts/team15_independent_gate.py checks required files and independently compares checkout content to integration for cross-team path overlap.
- CI source and scripts were committed, but no execution log, run URL, exit code or test count has yet been independently obtained.
- The audio inventory only checks what its own script implements. Browser sound, decoding, hosted functionality and real-device playback require separate evidence.
- Team13 browser test requires a browser/dependencies and is not included as a passing step in this workflow. Real two-device audio/video remains unverified.
- Team14 simulated settlement is not actual payment, refund or transfer.

## Provisional merge decision
11 HOLD: actual contract tests and role migration authorization proof required.
12 HOLD: asset decode, actual playback, full lesson paths and human approval required.
13 NEEDS FIX/REVIEW: role/approval compatibility, external room access security, browser and live device evidence required.
14 NEEDS FIX/REVIEW: persistent booking/transaction IDs, currency, idempotency scope and refund settlement reconciliation required.
15 HOLD: baseline divergence and CI execution evidence pending.

No production server, team-owned source, integration branch or deployment modified.
