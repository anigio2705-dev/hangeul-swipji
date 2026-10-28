# Team11 thirteenth pass — actual server booking gate integration

## Actual implementation
- Changed `phase3/server.py` method `Handler.booking` (actual existing server route helper). After fetching booking from DB, non-admin requests invoke `authenticated_booking_access(db,u['id'],bid,'view')` to verify the latest learner role, provider role/approval and booking ownership from authoritative database. On deny, raise existing server `Error` with 400/401/403/404/409 status. Admin behavior preserved.
- Added `phase3/test_common_server_booking_gate.py` (4 tests): actual Handler.booking accepts existing approved learner/provider, rejects unrelated learner, denies both after provider revocation, denies learner after role change.
- Existing 81 authored test methods retained, expected total **85**. Tests and workflow actual run not verified in this session. No claim of pass.
- Code commit `1b1da8756225af3fe89242d4b6b78817cc15a7b5`; test commit `6326b1dda7f8869b73a433a0bce35c75c87176bf`.
- No edits to instant auto-match, content, live deployment, production DB, real money, other teams' branches.

## Scope and limits
This is a **real server function integration**, not a completed HTTP end-to-end flow. It applies to routes that call `Handler.booking`; it does not automatically protect any independently implemented Team13 room endpoint or the separate `GET /api/bookings` list route. Existing admin bypass remains unchanged. The function uses server-supplied `u` from the authenticated session; it re-reads current DB role and approval.

## Team13 handoff
Use `team11_session_booking_bridge.authenticated_session_booking_access(db, raw_session_token, booking_id, action)` at the actual video room/join/completion endpoints. Cookie must come from server HTTP header and DB session. Deny before returning room URL or updating attendance; do not trust client IDs. Verify revocation on each request and existing auto-match remains intact. Team13 is responsible for its own route code and nonproduction E2E tests.

## Team12/14 handoff
Team12 must supply learning-progress storage API and reentry test; existing team11 schema has no proof of full learning-progress persistence. Team14 must validate Team13 server-authenticated completion event, booking and event ID and durable idempotency; no actual money.

## Progress evidence
Original 1–40 per-item score baseline remains in `docs/team11/TENTH_PASS_PROGRESS_1_40_20261028.md`, provisional mean 45.0%. Given actual booking gate wiring (item 33), provisional item 33 increases **80 -> 85** (real function wired, but unverified tests and full routes remain); item 29 increases **50 -> 60** (booking helper access improved, Team13 video endpoints not wired). Other 38 items unchanged. **New provisional mean = (1800+5+10)/40 = 45.375%, rounded 45.38%; increase +0.38 percentage points.** Do not claim 90/100 without CI and original completion conditions. 21–30 are Team13 owned and Team11 collaborative; count once in whole 160.

## Tests and blockers
Workflow: https://github.com/anigio2705-dev/hangeul-swipji/actions/workflows/team11-contract-tests.yml
**No specific Actions run ID / log / exit code verified** in this session. Actual HTTP end-to-end and room revocation require Team13. Production backup/restore, real two-device video/audio, actual payment, production deployment and human final review excluded from this pass.
