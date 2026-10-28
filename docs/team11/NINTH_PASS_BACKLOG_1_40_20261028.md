# Team11 ninth-pass evidence by original backlog number (2026-10-28)

Original numbering source: `docs/PLATFORM_EXECUTION_BACKLOG.md` on `docs/platform-execution-backlog-20261027`. Only team11-owned code changed.

## Actual changes and evidence
- `phase3/test_common_persistence_restart.py` commit `48cb0f2ac90c879f6ac483223ffab9a2d9a2ea80`: four NEW tests using checked-out real `schema.sql` and isolated on-disk temporary SQLite. Tests restart retaining learner/teacher/booking, revoked provider permission after reconnect, SQLite backup/restore integrity and booking uniqueness after reconnect. No production database access.
- Prior 50 methods retained; expected 54 methods under existing workflow `python -m unittest discover -s phase3 -p 'test_common_*.py' -v`.
- Actions workflow: https://github.com/anigio2705-dev/hangeul-swipji/actions/workflows/team11-contract-tests.yml . **Actual run URL, SHA, exit code and pass/fail counts not verified**; 54 is a count of authored methods, not a passing result.
- Existing server: `phase3/server.py` includes register, login, logout, provider review, approved-only search and booking gate; does NOT demonstrate end-to-end live account flow, email confirmation, password recovery, multi-role UI, cross-device persistence or operational backup.
- Team13 interface: `phase3/team11_shared_boundary.py` `authorize_student`, `authorize_provider`, `lesson_completion_event`, `validate_completion_event`. Provider approval must be checked against persisted user, not client-provided role.
- Team14 interface: `settlement_reference` uses `event_id`, `booking_id`, `month_id`, `lesson_index`, `currency=KRW`; downstream must enforce persistent idempotency and verified completion. No real payment/ledger call.
- No existing production server, other team files, integration/main, migration, merge or deployment modified.

## Number-by-number status (40 items; provisional statuses not PASS)
| No. | Status | Specific evidence or remaining blocker |
|---|---|---|
| 1 | 외부 확인 대기 | business objective in original backlog; HQ policy confirmation |
| 2 | 외부 확인 대기 | existing home preserved, public UI not retested |
| 3 | 외부 확인 대기 | original flow outline, complete journey not verified |
| 4 | 외부 확인 대기 | free vs paid display not browser-verified |
| 5 | 외부 확인 대기 | unapproved commission/reward terms |
| 6 | 외부 확인 대기 | referral business policy draft requires decision |
| 7 | 외부 확인 대기 | team division described; cross-team operations unverified |
| 8 | 수정 필요 | feature-level CI/public/device evidence ledger incomplete |
| 9 | 수정 필요 | full 160-item owner/evidence register not independently complete |
| 10 | 외부 확인 대기 | numbering preserved, HQ backlog approval |
| 11 | 외부 확인 대기 | current integration checkout not tested |
| 12 | 외부 확인 대기 | integration CI evidence unavailable |
| 13 | 외부 확인 대기 | Render service config not accessed |
| 14 | 외부 확인 대기 | owner Chrome settings not accessed |
| 15 | 외부 확인 대기 | production deployment prohibited |
| 16 | 외부 확인 대기 | /healthz live SHA not verified |
| 17 | 외부 확인 대기 | browser auth prompt regression not tested |
| 18 | 외부 확인 대기 | login/logout/reentry browser not tested |
| 19 | 외부 확인 대기 | origin and public API security not tested |
| 20 | 외부 확인 대기 | full public booking journey not tested |
| 21 | 외부 확인 대기 | team13 video route not browser tested |
| 22 | 외부 확인 대기 | two-party same-room unverified |
| 23 | 외부 확인 대기 | Jitsi host credentials unverified |
| 24 | 외부 확인 대기 | camera/mic device permission unverified |
| 25 | 외부 확인 대기 | actual two-person video/audio unverified |
| 26 | 외부 확인 대기 | real PC/mobile and owner final check |
| 27 | 외부 확인 대기 | media controls/rejoin unverified |
| 28 | 외부 확인 대기 | disconnect/reconnect service unverified |
| 29 | 수정 필요 | room URL/provider authorization not proven |
| 30 | 외부 확인 대기 | call and attendance evidence unverified |
| 31 | 외부 확인 대기 | isolated test DB exists; actual prod/test isolation unverified |
| 32 | 외부 확인 대기 | permanent DB vendor, cost and backup selection pending |
| 33 | 수정 필요 | role/approval code and tests exist; CI evidence missing |
| 34 | 수정 필요 | register/login/logout exists; verification/reset/recovery incomplete |
| 35 | 수정 필요 | legacy single role; multi-role UI and migration unapproved |
| 36 | 수정 필요 | unique email/id present; takeover safeguards unverified |
| 37 | 수정 필요 | provider gating exists; professional credentials process unverified |
| 38 | 외부 확인 대기 | temp restart tests authored; cross-device live persistence unverified |
| 39 | 수정 필요 | personal data deletion/retention workflow unverified |
| 40 | 외부 확인 대기 | temp SQLite backup/restore test authored; real backup/restore drill not done |

**Counts: 완료 0 / 개발 검사 통과 0 / 수정 필요 9 (8,9,29,33,34,35,36,37,39) / 외부 확인 대기 31 / 미착수 0.** These are conservative evidence-based classifications, not statements that all external features are unimplemented.

## Highest-priority blockers and owners
1. Team11 + HQ: obtain actual GitHub Actions logs for 54 tests; fix confirmed failures, rerun.
2. Team13: wire shared authorization boundary and verify login -> provider approval -> booking -> same-room behavior on its own branch.
3. Team14: consume completion event with persistent event_id dedup and booking reference on its own branch.
4. HQ: permanent storage provider and backup/restore drill environment decision; no operational DB access without approval.
5. HQ: decide multi-role persistence policy before schema migration; business approval required only for policy, money and deployment.
