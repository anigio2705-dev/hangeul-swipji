# Team11 — Eighth pass audit of backlog 1–40 (2026-10-28)

Source of numbering: `docs/PLATFORM_EXECUTION_BACKLOG.md` on `docs/platform-execution-backlog-20261027`. Statuses are conservative and do not imply live browser, Actions, backup/restore or human approval.

## Status inventory (1–40)
| No. | Status | Evidence / missing gate |
|---|---|---|
| 1 | 외부 확인 대기 | business goal written in backlog; policy finalization by HQ |
| 2 | 외부 확인 대기 | existing home; production preservation not retested |
| 3 | 개발 검사 통과 후보 | backlog documents role flow; full end-to-end not verified |
| 4 | 외부 확인 대기 | free/paid boundary documented; public UI unverified |
| 5 | 외부 확인 대기 | assumptions documented; business approval pending |
| 6 | 외부 확인 대기 | referral policy draft, approval pending |
| 7 | 외부 확인 대기 | work partition documented, team governance verification pending |
| 8 | 수정 필요 | CI/public/device evidence per-feature not consolidated |
| 9 | 수정 필요 | 160-item owner/evidence record not yet complete |
| 10 | 개발 검사 통과 후보 | source backlog preserves numbering; overall governance audit pending |
| 11 | 외부 확인 대기 | integration latest state not independently checked |
| 12 | 외부 확인 대기 | actual integration CI run evidence unavailable |
| 13 | 외부 확인 대기 | Render account settings not accessed |
| 14 | 외부 확인 대기 | owner-controlled Chrome settings not accessed |
| 15 | 외부 확인 대기 | deploy requires authorization |
| 16 | 외부 확인 대기 | live /healthz not inspected |
| 17 | 외부 확인 대기 | live authentication flow not inspected |
| 18 | 외부 확인 대기 | browser login/logout/re-entry not inspected |
| 19 | 외부 확인 대기 | public origin/API checks not executed |
| 20 | 외부 확인 대기 | public full flow not executed |
| 21 | 외부 확인 대기 | team13 owner; live route not verified |
| 22 | 외부 확인 대기 | team13 owner; two-party room not verified |
| 23 | 외부 확인 대기 | team13 owner; Jitsi moderator credentials not verified |
| 24 | 외부 확인 대기 | team13 owner; browser devices not verified |
| 25 | 외부 확인 대기 | two-party video/audio not tested |
| 26 | 외부 확인 대기 | human final verification required |
| 27 | 외부 확인 대기 | browser device toggles not tested |
| 28 | 외부 확인 대기 | team13 owner; reconnect recovery not verified |
| 29 | 수정 필요 | room-link/provider authorization not established by team11 |
| 30 | 외부 확인 대기 | video and attendance evidence not verified |
| 31 | 개발 검사 통과 후보 | schema and in-memory isolated tests; production DB isolation unverified |
| 32 | 외부 확인 대기 | permanent storage vendor/cost choice pending |
| 33 | 개발 검사 통과 후보 | team11 role/approval adapter and explicit decisions; CI unverified |
| 34 | 수정 필요 | server has register/login/logout; email confirmation/reset/recovery not verified |
| 35 | 수정 필요 | candidate multi-role exists but legacy DB single role; UI transition not implemented |
| 36 | 개발 검사 통과 후보 | users.id, UNIQUE email/referral_code; account takeover protections unverified |
| 37 | 개발 검사 통과 후보 | role/approval gating; credential verification policy unverified |
| 38 | 외부 확인 대기 | cross-device persistent profile/progress/booking not verified |
| 39 | 수정 필요 | privacy deletion and legal retention lifecycle unverified |
| 40 | 외부 확인 대기 | **no actual backup/restore drill**, schema-only evidence |

**Count (40):** 개발 검사 통과 후보 5 (3,10,31,33,36,37 = actually 6); 수정 필요 6 (8,9,29,34,35,39); 외부 확인 대기 28; 완료 0; 미착수 0. Correct count: **6 + 6 + 28 = 40**. Candidate statuses are *not* verified test PASS.

## Actual checked source evidence
- `phase3/schema.sql`: users.role single CHECK learner/partner/teacher/admin; approved boolean; UNIQUE email/referral code; sessions, bookings, ledger, audit, external_identities tables.
- `phase3/server.py`: /api/register validates email/password >=12 chars/role/adultConsent; session/login/logout; admin-only provider review; provider listing approved=1; bookings require learner role and approved provider; no role switch API found in inspected role-related code. No claim of complete authentication recovery or privacy deletion.
- `phase3/common_compat_adapter.py` and `phase3/team11_shared_boundary.py`: read-only legacy/candidate role projection and approval, completion event v1, HTTP error mapping; runtime integration still requires HQ/other-team coordination.
- `phase3/test_common_account_security_audit.py`: seven **new** isolated SQLite schema-based tests (not rewriting prior 43), checking legacy role compatibility, denied unapproved teachers, privilege isolation, CHECK and UNIQUE constraints, storage tables. Expected total **50** tests, **not executed in this session**.

## Persistent storage and backup separation (31–40)
Actual source: SQLite schema with tables, indexes and constraints. Not evidence of operational persistence across deployments, offsite backup, restore, RPO/RTO, account deletion, encryption, cross-device consistency or migration. Backup/restore 40 remains external verification waiting. No production DB or backup manipulation.

## 13/14 contract and conflicts
- 13: legacy approved teacher can be conversation provider; teacher has no implicit learner rights. API waiting/idle vs persisted offered/active/ended; booking completed event requires real booking IDs and authorization at service boundary.
- 14: month index and integer KRW simulation do not uniquely identify bookings/transactions; idempotency must be persisted on consumer side before any ledger mutation. No real payments.
- Need HQ approval for cross-team integration, persistent role migration, storage/backup vendor and operations.

## Evidence/HOLD
Branch `team11/common-foundation-20261028`. Actual CI workflow path: `.github/workflows/team11-contract-tests.yml`; run listing and dispatch unavailable in current connector. Actions URL: https://github.com/anigio2705-dev/hangeul-swipji/actions/workflows/team11-contract-tests.yml . **No run URL, exit code, or pass/fail counts verified.** Do not mark any of 1–40 as completed from this audit.
Changed code `phase3/test_common_account_security_audit.py`; initial commit `8a2b36ad060e90e6fba6dbb54fc28cf86ad72713`; test isolation fix `f20fb1242ce77466a603391c61fedcce73d1c210`.
