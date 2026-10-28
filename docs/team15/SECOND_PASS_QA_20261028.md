# Team15 independent quality gate — 2026-10-28

## Baseline and branch review
Baseline main: fe9759fd0f60f20e784fae1d3d95625b63db1d93.
Existing branches verified: team11/common-foundation-20261028 (36 commits ahead), team12/education-audit-20261028 (32), team13/platform-bfcache-reconnect-20261028 (33), team14/business-systems-audit-20261028 (33). Team15 expected branch did not exist when checked.
These ahead counts include shared prior development; they do NOT imply that every changed file belongs to the named team. Preserve all source branches and do not merge wholesale.

## Independent merge gate
- Team11: HOLD until single/multiple-role compatibility, ID/state/error contracts and contract consumers in teams13/14 are reconciled.
- Team12: HOLD until actual audio assets and browser playback, human listening approval, free 350 / professional 96 paths and answer/translation/progress are evidenced.
- Team13: HOLD until browser back/forward, refresh, disconnect/reconnect, expiry, duplicate match, authorization and real two-device calling are separately evidenced.
- Team14: HOLD until multi-session partial refunds, idempotency, reverse entries, double settlement and reconciliation tests are evidenced; real payments/payouts disabled.
No team is approved for deployment on this audit alone.

## Shared-file collision risks
Comparing each team against main yields overlapping files including phase3/instant-browser-test.cjs and phase3/test_instant_matching.py. This is a *potential integration collision*, not proof of a textual merge conflict. Compare team-specific commits and patch ancestry before cherry-picking. Common baseline files appear in all four branch comparisons.

## Core regression matrix
| Area | Automated checks required | Separate manual/live gate |
|---|---|---|
| Free learning | 350 unit IDs, representative routes, answers, translations, progress save/resume, role isolation | hosted UI desktop/mobile and multilingual review |
| Audio | file exists, URL resolves, click/keyboard event fires, playback promise resolves, no false human-voice label | human listening and real device/speaker |
| Matching | authorized booking, queue TTL, duplicate request, disconnect/reconnect, bfcache and refresh | two devices, real camera/mic, live signaling |
| Mock settlement | per-session amounts, partial cancel/refund, repeat refund idempotency, no double payout, reversal and total reconciliation | policy sign-off; real transfers must stay disabled |

## Verification evidence status
GitHub branch compare: completed. CI execution: NOT VERIFIED. Hosted server: NOT VERIFIED. Real devices: NOT VERIFIED. Payment rails: NOT ENABLED / NOT VERIFIED.
Merge verdicts are provisional HOLD, not failures established by executing tests.
