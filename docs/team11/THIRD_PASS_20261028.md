# Team11 third-pass: actual checkout execution and cross-team conflicts — 2026-10-28

## Evidence and exact command
GitHub connector read the **actual repository blobs** for phase3/common_contract.py, test_common_contract.py, test_common_compatibility.py, schema.sql and instant_matching.py. Team13 and Team14 branch sources were also inspected. Direct local `git ls-remote https://github.com/anigio2705-dev/hangeul-swipji.git` failed with `Could not resolve host: github.com` (exit 128). **Do not claim exact-checkout test PASS on this basis.**

Added `.github/workflows/team11-contract-tests.yml` on this dedicated branch. It uses `actions/checkout@v4`, prints `git rev-parse HEAD` and executes **exact checked-out source** with:
```bash
python -m unittest discover -s phase3 -p 'test_common_*.py' -v
```
The 15 pre-existing tests and four new isolated schema tests are included (19 expected methods). **At documentation time GitHub Actions job completion/logs were not verified: status UNCONFIRMED, not PASS.** Workflow is a test-only CI definition, not deployment.

## Existing schema and permissions
`phase3/schema.sql` stores one `users.role` (learner|partner|teacher|admin) and boolean `approved`. `phase3/instant_matching.py` branches on role: only learner is learner-side, partner/teacher are provider-side; approved is required for providers. Multi-role profiles cannot be projected into that model without explicit role selection and per-profile approval. The isolated `test_common_legacy_db.py` loads the **real checked-out schema** into in-memory SQLite and checks schema shape, exact singleton projection, non-escalation, and explicit migration gate. No real DB writes.

## Team13 and Team14 comparison
Team13: `instant_matches.id`, `learner_id`, `partner_id`, `room`; persisted states offered|active|ended; idle|waiting are response-only. API returns camelCase `matchId`, `roomUrl`, `expiresAt`; existing error uses Korean string + numeric 403/405/409, not candidate `{error:{code,message,requestId}}`. The common contract does not authorize changing these. Role `teacher` also qualifies as conversation provider when approved; provider-specific approval absent.
Team14: `Month(lesson_prices)` has no user_id, booking_id, month_id, lesson_id, currency, nor external transaction_id; indexes each lesson by **integer position**, operations keyed by `operation_id` string. It is a stand-alone simulation, not a database/API. `completed` and `refunded` are set/dict bookkeeping, not persisted transaction states. `ContractError(ValueError)` is not a shared structured API error. Amounts are positive integer **KRW**, whereas team11 calls them minor units with no currency; KRW has zero decimal minor digits. Idempotency signature is scoped to one Month instance only.
Team13 booking checks use `bookings.learner_id`, `teacher_id` and `status in ('in_class','test_paid')`; team14 monthly simulation has no booking linkage. Joining by lesson index alone would be unsafe.

## Contract collisions / shared files needing later approved change
1. `phase3/schema.sql`: users.role single-value and approved boolean; propose separate user_roles + teaching_profiles approval (migration and rollback required).
2. `phase3/server.py`: legacy booking authorization/status/error response; map to canonical API codes without breaking existing clients.
3. `phase3/instant_matching.py`: single-role eligibility, match ownership and response states; do not replace existing matching.
4. `phase3/team14_monthly_sim.py`: independent month/lesson/booking/transaction IDs, currency, idempotency scope, structured error adapter required before integration.
5. `phase3/common_contract.py`: enums are **candidate sets**, not validated transitions. ID regex may reject preexisting IDs; verify actual generated ID formats before enforcing.

## Next gates
Obtain GitHub Actions workflow run URL, checkout SHA, test logs, exit code; resolve any failures. Team13 to propose explicit role-selection and state transition mapping. Team14 to propose immutable ID linkage, money units, event/refund mapping and error adapter. HQ to approve migration/ownership before shared-file changes. No integration, deployment, production DB or payment activation.
