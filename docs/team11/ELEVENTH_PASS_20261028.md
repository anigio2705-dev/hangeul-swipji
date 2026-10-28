# Team11 11th pass — server-side DB authorization integration

## Changed files
- `phase3/team11_server_booking_adapter.py` — actual SQL reads of `users` and `bookings` using a server-provided authenticated session user ID, never request JSON roles.
- `phase3/test_common_server_booking_adapter.py` — 9 new isolated real-schema SQLite integration tests for booking participants, outsider, nonexistent user, revoked provider, changed learner role, cancelled booking, completion authorization, malformed ID.
- Existing 64 tests retained; **73 test methods expected** in `python -m unittest discover -s phase3 -p 'test_common_*.py' -v`.

## Integration interface for Team13
`authenticated_booking_access(db, session_user_id, booking_id, action)` returns `{allowed: bool, code: string|null}`. Team13 must derive `session_user_id` from server-side verified cookie/session, not client input. Load all rows from the same trusted database transaction. Reject all non-allowed decisions before returning any room URL, attendance or booking data. Existing instant auto-matching is untouched. Team13 owns actual API wiring and live route tests; Team11 does **not** claim it is connected.

Actions `join` requires test_paid/in_class, `complete` requires in_class and provider actor, `view` supports known states, `settle` denied. Provider approval revoked denies both parties from entering even if booking still exists. A role change on an existing learner booking denies access. Error codes: VALIDATION_ERROR, NOT_FOUND, UNAUTHENTICATED, FORBIDDEN, CONFLICT, INVALID_STATE.

## Integration interface for Team14
Use `team11_shared_boundary.lesson_completion_event` and `validate_completion_event` with unique event_id and booking_id; do not derive money from client. Only server-authorized completed lessons may be emitted by Team13. Team14 must implement persistent event_id idempotency in its own code. No actual payment.

## Evidence and status
- Code commit `91685d04b5c40463c58cf481bc39e8010d1d79d6`
- Tests commit `8436ce8c33f97dcaec42fde3cbb461e619216c8a`
- CI workflow URL: https://github.com/anigio2705-dev/hangeul-swipji/actions/workflows/team11-contract-tests.yml
- **No specific Actions run URL, actual pass/fail count or checkout SHA verified in this session.** Tests written != tests passed.
- Operational DB persistence, learning progress across reconnect, email confirmation/reset, multirole storage, production backup/restore, actual browser video call all unverified or pending.
- No other team files, main, integration, production DB, payment or deploy changed.

## Progress and ownership
40 original items retain last 10th-pass provisional per-item percentages in `docs/team11/TENTH_PASS_PROGRESS_1_40_20261028.md` (mean 45%). Since Team13 has not integrated this new adapter and actual CI remains unverified, **do not inflate scores from writing this helper**. 11th-pass provisional team11 average remains **45.0%**; change against 10th-pass: **0 percentage points pending integration proof**. Team13 owns original 21–30 and Team11 collaborates, do not double count for overall 160.

## Next
1. Obtain actual Actions run and resolve failures.
2. Team13 wires this DB authorization into real API routes, verifies both participants same room and revoked provider rejection.
3. Team11 independently verifies full signup/login/admin approval/booking flow against isolated server test environment.
4. Coordinate learning-progress persistence with Team12, simulated settlement events with Team14.
5. HQ handles operational DB backup/restore environment and multirole migration policy; no unauthorized production changes.
