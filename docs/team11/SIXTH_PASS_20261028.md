# Team11 — sixth pass common boundary (2026-10-28)

## Scope and interface
Team11-owned code only: `phase3/team11_shared_boundary.py` and `phase3/test_common_shared_boundary.py`. No changes to team13/14 code, DB, server, main, integration, merge or deployment.

Version `team11.v1`:
- `authorize_student(user, candidate=False, approvals=None) -> AccessDecision(allowed,error_code)`
- `authorize_provider(user,kind,candidate=False,approvals=None) -> AccessDecision`
- `lesson_completion_event(event_id,booking_id,learner_id,provider_id,kind,amount_krw,state='completed') -> dict`
- `validate_completion_event(event) -> dict`
- `settlement_reference(event,month_id,lesson_index) -> dict`
- `http_error_contract(status) -> {code,http_status}`
- `match_state_contract(state) -> {state,persisted}`

## Contract details
Legacy `users.role` stays singleton and `users.approved` remains the legacy gate. Candidate multi-role access requires explicit per-kind approval; no implicit learner/teacher role elevation. The legacy teacher may serve as conversation partner, matching the prior instant-matching service's role eligibility; candidate teacher does not automatically receive a partner role.

`lesson.completed` event fields exactly: `contract_version=team11.v1`, `event_type=lesson.completed`, `event_id`, `booking_id`, `learner_id`, `provider_id`, `lesson_kind`, `booking_state=completed`, `amount` integer KRW, `currency=KRW`. This is a simulated event schema, **not** a settlement or actual payment. Receiver must persist event_id deduplication before applying settlement. Month reference adds `month_id` and nonnegative `lesson_index`; index is not a global lesson ID.

Errors: unauthorized role -> FORBIDDEN, invalid lesson kind -> VALIDATION_ERROR; legacy HTTP 400/401/403/404/409 maps to VALIDATION_ERROR/UNAUTHENTICATED/FORBIDDEN/NOT_FOUND/CONFLICT. Unsupported statuses fail closed. Match idle/waiting are API states only; offered/active/ended persisted.

## Regression and evidence
- Prior 31 methods (21 HQ-confirmed earlier, 10 added in fifth pass) retained; 11 new `test_common_shared_boundary.py` methods; expected **42** total.
- GitHub Actions exact checkout workflow `.github/workflows/team11-contract-tests.yml` runs `python -m unittest discover -s phase3 -p 'test_common_*.py' -v` on team11 branch push. The sixth-pass push should trigger it **if Actions enabled**.
- Actual Actions run URL, checkout SHA, exit code and pass/fail counts: **not obtained**. No assertion of PASS. Source execution remains HOLD until logs are reviewed.
- The code was committed without executing GitHub-hosted CI through this connector; no Actions dispatch/list-runs action available here.

## Conflicts/HOLD
- Team13 existing matching uses single-role and boolean approved; no runtime import of new boundary yet. Automatic matching preserved.
- Team14 simulation has no durable booking/event ID linkage and no persisted idempotency after restart. New event contract is only a handoff specification; team14 must implement durable dedup on its own branch.
- Existing users.role cannot persist multi-role. No migration authorized.
- Real payments, commission/referral rates, production deploy and human video-call verification remain HOLD.

## Commit evidence
- Shared boundary `5769765a7002967670de4e94d3ac15aa3a0c0059`
- Eleven tests `1a323d574b85b16c7cfcd65f52012d61595e42e4`
