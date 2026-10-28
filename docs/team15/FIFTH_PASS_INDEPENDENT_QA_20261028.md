# Team15 fifth-pass independent QA — 2026-10-28

## Verified CI evidence
Run: https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40611068471
All seven independent jobs succeeded:
- source-gate job 122562436836: success; integration SHA 2ca95fa1aa8206ec8763443d8256ab54ac789017, team11 96672116b0c87e34478233d1cf08028413515ff8, team12 f14b3df68224b8508d0c4fe6d7e8ba84277cd6a6, team13 5c464829dd93e70a8af534ea5e1d0d9ce9bd92f0, team14 e4d912c0752aa1bda1e67831a20e4e5e310be9f5. Source gate says no cross-team changed-file overlap at these SHAs.
- team11-contract job 122562436568: success, 21/21 tests.
- team12-audio job 122562436659: success; audit script completed, but 399 sound files human listening and browser playback are NOT certified.
- team13-python job 122562436646: success, 86/86 tests.
- team13-browser job 122562436319: success; mocked browser automation, not two real devices.
- team14-monthly job 122562436592: success, 14/14 tests; mock settlement only.
- integration-baseline job 122562436641: success, 84/84 tests.

## Newest branch HEADs (NOT tested by the above run)
- team11/common-foundation-20261028: 0ab299a0a116040ad5605150d11f6d454d038042
- team12/education-audit-20261028: b99873fd702410a3f53ba22d50953cc8c5ed58a4
- team13/platform-bfcache-reconnect-20261028: 2c8c6b0834af31d21a9104fce9bda2b0e04c819c
- team14/business-systems-audit-20261028: e4d912c0752aa1bda1e67831a20e4e5e310be9f5
The three newer team HEADs are ahead of the pinned CI refs. No assertion of their fifth-pass test success without run evidence. Avoid repeating unchanged pinned tests until new changes are ready.

## Compatibility gate
GitHub integration-to-branch comparisons show independent changed paths for teams 11-14, but source-path non-overlap is NOT API/schema compatibility.
11 <-> 13: single legacy users.role/approved versus multi-role/role-scoped approval; booking and match state transitions and provider eligibility need explicit adapters.
11 <-> 14: error codes, ID formats, money units and persistent transaction semantics need reconciliation.
13 <-> 14: instant match and booking/session IDs cannot be inferred from monthly lesson index; duplicate booking, refund and room access need end-to-end checks.
12: 399 inventory status, real audio decode/browser playback, 350 lessons/1758 quizzes/600 readings/96 pro lessons need independent content and learning-path validation.

## Status
PASS: pinned CI regression baseline and isolated job separation.
FIX: cross-team contract adapters, room authorization, booking/transaction persistence before integration.
HOLD: latest team11/12/13 changes until matching SHA-specific CI evidence; human audio approval, public server, real devices, real payment rails, integration and deployment.

## 160-item backlog evidence candidates (no completion claimed)
Candidates for HQ review: independent CI separated into seven jobs; baseline 21 common contract tests; baseline 86 matching-related Python suite; baseline 14 mock settlement tests; baseline 84 integration Python tests; audio audit script execution. Match these to exact numbered master backlog entries before changing statuses.
Not completed: cross-team multi-role/booking/payment compatibility, human audio review and missing assets, end-to-end 350/1758/600/96 curriculum, real two-device call, production billing/refund, live server verification, authorized merge/deployment.

No production changes, no merge, no deployment. Final approval remains with owner.
