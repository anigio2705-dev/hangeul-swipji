# Team11 fifth pass — real compatibility adapter, 2026-10-28

## Actual implementation
- `phase3/common_compat_adapter.py` (new): read-only `IdentityView`, `from_legacy_user`, `from_candidate`, `matching_side`, `normalize_match_state`, `normalize_error`, `month_lesson_reference`. Uses existing `common_contract.py` validators. Does not import server, access DB, migrate records or alter existing matching behavior.
- `phase3/test_common_compat_adapter.py` (new): 10 new tests, not rewriting existing 21. Checks legacy learner/provider separation, approval gating, candidate multi-role explicit approval, invalid roles/flags, matching state persistence distinction, HTTP errors and KRW-only simulation reference.
- `.github/workflows/team11-contract-tests.yml`: existing checkout workflow retains `python -m unittest discover -s phase3 -p 'test_common_*.py' -v`; label updated to 31 tests.

## Cross-team field mapping
| Common adapter | Team13 existing | Team14 existing | Limitation |
|---|---|---|---|
| `from_legacy_user(role,approved)` | users.role + users.approved | no roles | pure projection; no new learner rights |
| `matching_side(view,'provider')` | partner/teacher and approved | no provider check | not wired into Team13 runtime |
| `normalize_match_state` | idle/waiting API; offered/active/ended stored | not applicable | no transitions enforced |
| `normalize_error(403/409)` | server.Error with numeric status | ContractError(ValueError) | read-only mapping; no response conversion |
| `month_lesson_reference(month_id,index,'KRW')` | booking_id separate | Month index and KRW prices | no transaction/booking linkage, no cross-currency conversion |

## Test evidence and limits
HQ reports previous 21 tests passed; accepted as external reported evidence, not independently re-claimed. New expected total 31 methods. GitHub Actions exact-checkout command: `python -m unittest discover -s phase3 -p 'test_common_*.py' -v`.
GitHub connector `fetch_commit_workflow_runs` returned empty for SHA `9e828e360dbbd6eec8156817b9bda2cf9dfa80d2`; that endpoint is PR-filtered and cannot establish push-workflow status. This session has no GitHub Actions dispatch/list-runs action, and direct git checkout previously failed DNS. **New 10 tests remain UNVERIFIED; no workflow URL, test exit code or pass/fail counts available.** Never substitute reconstructed code. To complete: authorized operator open https://github.com/anigio2705-dev/hangeul-swipji/actions/workflows/team11-contract-tests.yml and dispatch team11 branch, then inspect run SHA/log and 31-test results. If the workflow isn't visible, check repository Actions enablement and workflow registration on default branch.

## Conflict and integration gate
Single users.role and approved boolean cannot encode distinct provider approvals. Candidate multirole must be explicitly provisioned and approved; legacy users never gain extra roles automatically. Team13 runtime still uses single-role branch logic and should remain untouched until separately approved. Team14 lacks stable month/lesson/booking/transaction IDs, currency and API error adapter; simulation only. No shared server, schema, team13/team14 files, main, integration, production DB, merge or deploy changed.

## Commits
- Adapter: `bfb28c447d8dca0d91c4cbdf055f520f039276b9`
- New tests: `d62cd48b8aac39f79078e2fca9b4fcccbd79d902`
- Workflow label: `9e828e360dbbd6eec8156817b9bda2cf9dfa80d2`
