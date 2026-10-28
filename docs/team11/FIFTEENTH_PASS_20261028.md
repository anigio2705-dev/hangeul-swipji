# Team11 15th pass — live attendance gate and settled history

## Actual changes
- `phase3/server.py`: existing POST `/api/bookings/{id}/join` and `/attendance` routes now call `authenticated_booking_access(db,uid,bid,'join')` immediately before attendance mutation, checking DB-owned participant IDs, current roles and provider approval. The existing authenticated `Handler.user` cookie/session flow is unchanged; instant matching is untouched.
- `phase3/team11_booking_access.py`: allow authorized `view` of `test_settled` booking history; `join` remains denied for completed/settled status.
- `phase3/test_common_booking_state_access.py`: three new tests for settled view, denied settled join, revoked provider denied for old booking.
- Code commits: `f96a4d64b17ffb7a80fd0e213d7ede2556628486`, `71bad35c12fd61d549312f55a82f78fc44789238`; test commit `a61f64d5fdc57649b4aaa2601e0f8d37ad167ab3`.

## Verification
- Existing 88 authored methods retained; 3 added, **91 authored tests expected**.
- Actual CI run result for this commit, full HTTP E2E and restart tests **not independently observed** in this session. Do not mark passed.
- Prior 14th pass provisional team11 45.50%. Increase item #33 from 85 to 87% for added live attendance gate and settled-state fix; other 39 unchanged. New provisional mean **45.55%**, increase **+0.05 percentage points**. Team15 must verify against original 160-item backlog and actual Actions run before official use.
- Original per-item baseline: `docs/team11/TENTH_PASS_PROGRESS_1_40_20261028.md`. Overrides: 13th #29=60, #33=85; 14th #36=75; 15th #33=87. Count collaborative 21–30 only once under Team13 in whole-160 aggregation.

## Team13 contract
- Call `authenticated_session_booking_access(db, hs3_cookie, booking_id, action)` from trusted cookie and server DB, or `authenticated_booking_access(db, authenticated_uid, booking_id, action)` after server session auth.
- `view` for historical records, `join` only test_paid/in_class, `complete` only in_class and provider. Deny before disclosing room link or mutating attendance.
- Team13's independent room endpoints and real multi-team branch merge remain unverified. Existing instant match must not be modified.

## Outstanding
- Actual GitHub Actions run logs and 91 tests, live HTTP end-to-end, reconnect and restart persistence for learning progress.
- Team13 room API integration, Team14 authenticated event-to-ledger integration, Team15 independent branch merge.
- Admin history access and provider-revocation historical visibility need a product policy distinction; room access must remain revoked.
- No production, real payments, main branch or other team branch changed.

Workflow: https://github.com/anigio2705-dev/hangeul-swipji/actions/workflows/team11-contract-tests.yml
