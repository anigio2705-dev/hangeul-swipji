# Team11 fourteenth pass — actual bookings list endpoint access gate

## Implemented
- `phase3/server.py`: GET `/api/bookings` now filters each booking through `authenticated_booking_access(db, uid, b['id'], 'view')`, which loads current DB role/approval and booking ownership. Unauthorized records are not serialized, including after provider revocation or learner role change.
- `phase3/test_common_booking_list_route.py`: 3 new route-level regression tests using isolated real schema SQLite: approved parties list booking, provider revocation hides from both, changed learner role hides existing booking.
- Code commit `1a6c5040b85349a0158637f77c7a2011523f9b39`; test commit `3844fec5a28268f4bef53142e9a46aa1315bd55a`.
- Existing 85 authored methods preserved; 88 expected total. Actual GitHub Actions run ID, success/failure, runtime HTTP results **not verified in this session**.

## Scope and handoff
- Team11: real server booking-detail helper from pass 13, booking-list route from pass 14. Booking creation already obtains server-authenticated `u` and checks approved provider and time conflicts in existing `server.py`; no duplicate implementation.
- Team13: video room and attendance endpoints must invoke shared DB/session boundary and deny before returning room link. Instant auto-match remains unchanged.
- Team12: full learning progress persistence/reconnect requires its own owned storage route evidence; not claimed by Team11.
- Team14: event-to-ledger integration and durable idempotency remain Team14 responsibility.
- Caveat: this list filtering may hide bookings from revoked providers, including their own history. Team13/HQ should define an authorized historical view distinct from room access; never use history visibility as a reason to grant room access.

## Item-level progress
Original 1–40 item-by-item baseline in `docs/team11/TENTH_PASS_PROGRESS_1_40_20261028.md`. 13th pass overrides: #29 60%, #33 85%; all other 38 unchanged (mean 45.375%). 14th pass provisional: #33 **85 -> 90% is NOT justified** without actual verified tests. Keep #33 85%; #36 **70 -> 75%** due server listing data isolation, though final verification pending. New mean **45.50%**, increase +0.125 percentage points (rounded +0.13 pp). Scores remain provisional and subject to Team15 independent evidence review. 21–30 jointly supported but count once in whole 160.

## Outstanding
- Actual CI run results, all 88 test outcomes, server HTTP E2E and account restart verification.
- Team13-owned room access, cancellation, matching.
- Operational data backup/restore and cross-device learning progress.
- No main/integration, production, real payments, live video, or other team branch changes.

Workflow: https://github.com/anigio2705-dev/hangeul-swipji/actions/workflows/team11-contract-tests.yml
