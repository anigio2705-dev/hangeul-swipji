# Team13 second-pass regression review — 2026-10-28

## Scope and evidence
Base branch: integration/phase2-phase3-20261027. Dedicated branch: team13/platform-bfcache-reconnect-20261028.
Existing pagehide fix resets the timer handle to null after clearInterval, allowing pageshow to call poll again.
Added browser regression checks for synthetic pagehide/pageshow, reload while waiting, and explicit cancellation. These do not replace a real browser history-navigation or two-device media test.
Added HTTP regression cases for unapproved partner exclusion, no room URL disclosure, expired presence cleanup and explicit rejoining. Existing test_instant_matching.py already covers concurrent join, foreign ready, stale offers, booking isolation and consent.

## Verification status
Code committed; no local Python/Playwright execution was available in this connector-only session. All newly added cases are **UNRUN**, not PASS. Run:
- python3 -m unittest discover -s phase3 -p 'test_*.py' -q
- node phase3/instant-browser-test.cjs
Record command exit status, browser errors, results JSON and commit SHA before merging. Do not deploy.
Browser test uses intercepted Jitsi provider responses; it does not verify real audio/video.

## Contracts and risk
Team11 shared ID/role/permission contract has not been independently retrieved or approved in this pass. Existing instant_matching.py uses users.id, learner/partner/teacher roles and users.approved; booking ownership uses bookings.learner_id/teacher_id. A single role per account and the meaning of approved may conflict with Team11's proposed multi-role model. Confirm mapping and approval scope with Team11 before changing shared DB/schema.
Jitsi room URLs are bearer-like capabilities: application API restricts disclosure, but the external Jitsi room itself has no independently verified participant authentication. Do not describe the HTTP checks as provider-level room authorization.
Reserved-class room permissions and monthly-package policies need separate existing server tests and Team14 rules; not certified in this pass.
No changes to production, Render configuration, main, integration, shared schema or payment.

## Next
Execute the tests in a checked-out workspace; inspect failures. Add real back/forward browser navigation, offline/network interruption, scheduled-class authorization checks and dual-device media verification as distinct evidence.
