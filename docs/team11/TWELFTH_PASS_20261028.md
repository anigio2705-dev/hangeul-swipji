# Team11 12th pass — authenticated session-to-booking contract

## Implemented
- `phase3/team11_session_booking_bridge.py`: `authenticated_session_booking_access(db, raw_session_token, booking_id, action, now=None)`. Hashes hs3 cookie token with SHA-256; checks live sessions table expiry; loads server-owned user ID; delegates to DB-backed booking authorization; fail-closed response `{allowed,code}`. No client-provided roles, user IDs, approval flags or booking participants trusted.
- `phase3/test_common_session_booking_bridge.py`: eight new tests covering both legitimate sessions, other user, expired token, malformed/unknown token, revoked provider, unauthorized completion, role change, cancelled booking. Test-token length corrected in commit `1994f8f45a21d2f73269934cd7703f54be1b7ffe`.
- Existing 73 test methods retained. Expected total **81 authored methods**. Actual CI run status **not verified here**; no claim of PASS.

## Team13 integration contract (required)
1. Extract `hs3` cookie server-side using existing trusted HTTP cookie parser; do NOT take token from request JSON or query.
2. In the same DB transaction as the room/booking operation call `authenticated_session_booking_access(db, cookie_token, booking_id, action)`.
3. Deny all `allowed=False` results before returning room URL, altering attendance or marking lesson complete. Map codes UNAUTHENTICATED=401, FORBIDDEN=403, NOT_FOUND=404, INVALID_STATE=409, CONFLICT=409, VALIDATION_ERROR=400.
4. Keep existing instant automatic matching unchanged. On revocation, existing live room links may still be reusable at video-provider layer; Team13 must independently verify/provider-enforce revocation and prevent leakage. This helper alone does not revoke Jitsi URLs.
5. Test real HTTP routes and 2-account same-booking same-room; Team11 has not changed Team13-owned handlers.

## Team14 integration contract
Team13 emits validated server-owned completion event `team11_shared_boundary.lesson_completion_event`; include unique `event_id`, `booking_id`, provider/learner IDs, amount in KRW and state. Team14 must reject duplicates with durable event ledger and verify authoritative booking status. No real payments.

## Item-level progress
Keep original 1–40 individual baseline from `docs/team11/TENTH_PASS_PROGRESS_1_40_20261028.md`, mean 45.0%. Session bridge implementation advances boundary readiness, but because actual API wiring, CI logs and restart/service verification remain outstanding, **no evidence-based numerical increase is claimed**. Provisional 12th pass mean **45.0%**, change **0.0 percentage points**. Original 21–30 owned by Team13 with Team11 collaboration; count once in 160.

## Outstanding
- Actual HTTP route wiring and E2E tests (Team13).
- Actual Actions workflow run URL, exit code and pass/fail count (Team11/HQ).
- Reconnect and server-restart persistence for learning progress and profile in real service (Team11/12).
- Production backup/restore and multi-role schema migration (HQ approval).
- Actual video/audio, live money, production deployment (HOLD).

## Evidence
- Code commit: `2d42e00eb5fce314aa6f23f65cf59ab3b77b4bb6`
- Tests: `2eea7bb15ecd065312cc39a410fa4f1cedd8d820`
- Test token fix: `1994f8f45a21d2f73269934cd7703f54be1b7ffe`
- Workflow: https://github.com/anigio2705-dev/hangeul-swipji/actions/workflows/team11-contract-tests.yml
- No production, main, integration, other-team, DB migration or payment changes.
