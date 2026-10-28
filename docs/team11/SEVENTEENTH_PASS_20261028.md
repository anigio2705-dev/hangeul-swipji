# Team11 17th pass — booking HTTP regression fixture repair

## Root cause
`phase3/test_common_http_booking_integration.py` uses a class-scoped SQLite DB and live loopback HTTP server. Individual tests mutate persistent shared fixture rows: `test_missing_and_expired_sessions` expires outsider's session; `test_revocation_hides_existing_booking` revokes teacher approval. unittest executes test methods alphabetically, so `test_outsider_cannot_list_other_booking` receives HTTP 401 instead of 200 and `test_student_sees_only_own_booking` sees zero rows after approval revocation. This is test-state leakage, not evidence of a live authentication bug.

## Fix
Added per-test `setUp` resetting fixture session expiry, teacher approval and learner roles before each HTTP request sequence. Assertions unchanged. Tests retained. The production server implementation and security checks were not weakened.
- Code commit: `bef292465e5de35aec8d5051cbb58efdc6c34d0f`.
- Prior expected test count: 96; current expected count: 96 (no tests added or removed).
- No confirmed GitHub Actions run ID yet. Commit-workflow lookup returned empty (only PR-triggered runs are surfaced). Local runtime could not access GitHub host, so no execution evidence obtained. **PASS NOT CLAIMED.**

## Integration scope
The existing HTTP suite starts the real `server.Handler` and exercises cookie session, DB lookup, authorization and booking-list JSON. Team13 room endpoints and Team14 settlement have not been combined on this Team11 branch. Team15 should run the two formerly failing tests plus all Team11 tests on its nonproduction integration branch, then record actual job URL and pass/fail counts.

## Provisional item progress
Baseline original 1–40: `docs/team11/TENTH_PASS_PROGRESS_1_40_20261028.md`. Overrides: #29=60, #33=87, #36=75; remaining items unchanged. Mean remains **45.55%**, change **0.00 percentage points** pending green CI. Do not count collaborative #21–30 twice in 160-item rollup.

## Remaining work
- Verify CI and full 96-case regression, then correct any further failures.
- Full HTTP register/login/teacher approval/booking creation/cancellation, session expiry and progress persistence across process restart.
- Team13/14 code integration, event-to-ledger, and Team15 160-item independent audit.
- No main, production deployment, instant auto-match, content, live payment or real video changes.
