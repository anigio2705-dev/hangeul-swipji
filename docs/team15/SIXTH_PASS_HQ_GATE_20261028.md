# Team15 sixth-pass HQ baseline and approval gate — 2026-10-28

## Baseline refs independently verified with GitHub compare
Integration 2ca95fa1aa8206ec8763443d8256ab54ac789017
Team11 183a318e6600a2be8835943f067fe7c3d6ac8fa8
Team12 b99873fd702410a3f53ba22d50953cc8c5ed58a4
Team13 8a49b4b42fcefcfeaeb44cf531251d2ae5d3b9d2
Team14 ab05d827c2d5ba847bcc2dcd06922640846c126b
All four have the integration baseline as common ancestor (behind 0). No same-path overlap among these four teams' GitHub comparison file lists; this is not proof of semantic contract compatibility.

## Independent CI
Updated .github/workflows/team15-independent-regression.yml in commit 5a00c01893bee40da0ce765c47db696e4fdfeb1f. Seven independent jobs pin these immutable SHAs: source gate, 11 contract, 12 audio, 13 Python, 13 browser, 14 monthly, integration baseline.
A push event is configured. The new run URL and test exit results have not yet been obtained; do NOT claim PASS. Prior run 40611068471 (7 successes) tested OLDER SHAs, so it does not certify this baseline.

## Sixth-pass post-change gate
Once each team submits its actual sixth-pass commit, pin those exact SHAs in a NEW verification commit and run all independent jobs. Evaluate both baseline and new change, including:
- 11->13 role scope, teacher approval, privilege escalation, existing member compatibility
- 13->14 booking/session/completion identifiers, event idempotency, monthly ledger, refund/retry/restart
- 12->13 free learning progress to partner/teacher selection, no missing/duplicate course link
- content 350 lessons, 1758 quizzes, 600 readings, 96 pro sessions; audio missing 354 and human review pending
- preserve instant matching, browser reconnect, mock settlement (22 expected in sixth-pass), no real payments
Record per-job SHA, URL, PASS/FIX/HOLD and evidence; do not infer tests from documentation.

## HQ approval request (status HOLD, no owner contact)
Department: Team15 quality and operations
Request: HQ to confirm shared event/API contracts for multi-role approval, booking/completion, currency/refund semantics and cross-team acceptance criteria before authorizing integration.
Reason: isolated tests cannot prove cross-team transaction correctness.
Risk: permission escalation, duplicate payouts, invalid room access, data migration breakage.
If not approved: cross-team integration and production readiness remain HOLD; isolated testing continues.
Recommendation: HQ approves only technical schema review and contract fixtures; business policy, real payment, production deploy and human audio/real-call signoff remain owner HOLD.
No other-team branch writes, merge, deployment or payment activity performed.

## 160-item backlog
Candidate only: SHA-pinned isolated CI and baseline test evidence, subject to exact backlog item mapping. HOLD: end-to-end integration, human listening, live two-party call, real payment/refund, production deployment. No status changed without verification.
