# Team11 Fourth Pass — 2026-10-28

## Execution and evidence (do not claim PASS)
- Branch: `team11/common-foundation-20261028`; integration/main untouched.
- Actual branch workflow `.github/workflows/team11-contract-tests.yml` verified via GitHub connector. Trigger: `push` on exact branch and `workflow_dispatch`; job uses `ubuntu-latest`, `contents: read`, `actions/checkout@v4` and `actions/setup-python@v5`. No secret, deployment, write permission or operational DB use.
- Command in workflow: `python -m unittest discover -s phase3 -p 'test_common_*.py' -v`; prints `git rev-parse HEAD` and `git status --short`. Expected **21** methods after two new security tests (7 + 8 + 6).
- GitHub connector `fetch_commit_workflow_runs` for prior SHA `994e173f333d3735e8c7adfe10be90a9cc94fbc4` returned `workflow_runs: []`. This API filters PR-triggered runs, so empty results **cannot prove** push runs did not occur. No workflow URL, run SHA, job log or exit code verified. Result: **UNVERIFIED**, pass/fail counts unavailable.
- Container command `git ls-remote https://github.com/anigio2705-dev/hangeul-swipji.git HEAD`: exit **128**, `Could not resolve host: github.com`. This is a network/DNS checkout failure, **not a test failure**.
- Safe alternative: open https://github.com/anigio2705-dev/hangeul-swipji/actions/workflows/team11-contract-tests.yml, select branch and Run workflow (if workflow is recognized). Otherwise an authorized GitHub Actions maintainer can enable Actions/approve first-time workflow and push a test-only change on team11 branch. Record run URL, exact checkout SHA, job exit code and full 21-method output. Do not run against live DB. This connector exposes no workflow-dispatch action; no remote execution is asserted.

## Team13/Team14 compatibility mapping
| Field | Team11 candidate | Team13 actual | Team14 actual | Decision/gap |
|---|---|---|---|---|
| Identity | opaque string user_id; separate match_id/booking_id | users.id, instant_matches.id, matchId response; booking learner_id/teacher_id | Month has no user_id, booking_id or transaction_id; lesson by integer index | IDs must be added via approved adapter; never infer identity from lesson index |
| Roles | learner/partner/teacher/admin set; per-profile approval candidate | single users.role, approved boolean; teacher and partner eligible as provider | no user/role | single-role projection read-only; no implicit extra roles |
| Match state | idle/waiting/offered/active/ended | idle/waiting API-only; offered/active/ended stored | none | distinguish response vs persisted |
| Booking | reserved/test_paid/in_class/completed/refunded etc candidate | bookings.status; in_class and test_paid used for exclusion | complete(index), refund(index,amount) | not equivalent to booking state; require explicit mapping |
| Currency | integer minor units + ISO currency candidate | bookings.price integer; currency implicit | positive integer KRW only | KRW has zero minor decimal digits; reject unapproved conversion |
| Transaction | pending/authorized/captured/refunded etc candidate | no canonical transaction API in instant matching | completed set/refunded dict, append-only simulation entries | cannot map automatically to transaction state |
| Idempotency | request/operation ID proposed | matchId for ready, queue dedupe | operation_id scoped to one Month instance | scope must be persisted for real financial writes |
| Errors | structured code + HTTP status candidate | server.Error(message, 403/405/409) | ContractError(ValueError) | adapters needed; avoid changing existing client response now |

## Legacy security and regression tests
`phase3/test_common_contract.py`: 7 methods.
`phase3/test_common_compatibility.py`: 8 methods.
`phase3/test_common_legacy_db.py`: 6 methods, loading real checked-out `schema.sql` in isolated SQLite memory. Tests legacy role shape, exact round-trip, no implicit teacher approval, multi-role migration gate, unapproved/rejected/suspended partner exclusion, SQL CHECK rejects multi-role/unknown role. **Written, not yet executed from checkout.**

## Collision/ownership and minimum changes
- `phase3/schema.sql`: single `users.role`, `approved` boolean; future migration to user_roles + provider approvals only after HQ approval.
- `phase3/server.py`: booking authorization and legacy errors; future adapter required.
- `phase3/instant_matching.py`: eligibility uses single role and boolean approval; future adapter must not alter current auto-matching without tested migration.
- `phase3/team14_monthly_sim.py` (other branch): month/lesson IDs, booking linkage, currency and idempotency namespace missing by design; remain test-only.
- `phase3/common_contract.py`: enums are candidate membership checks, not state-transition validation; no verified failure to justify altering implementation.
- Changed in this pass only: workflow test-step label; `phase3/test_common_legacy_db.py` (+2 tests); this report.
- No production DB, server, main, integration, payment, or deployment changes.

## Pending
Obtain real GitHub Actions job evidence; if job fails, reproduce and minimally fix only confirmed failure. Confirm workflow visibility/settings and branch Actions policy with authorized maintainer. 13/14 team leads and HQ must approve identity, permission, currency and error mappings before integration.
