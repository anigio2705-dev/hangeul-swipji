# HQ A — 160-task ledger supplemental READY decisions (2026-10-31, P0)

**Authority:** A central independently compares the original task text in `automation/hq_backlog_160.md` and `docs/HQ_160_DEVELOPMENT_CONTRACTS_20261029.md` with B/15 exact-SHA QA evidence. Original 160 task numbering and original backlog are unchanged. These are **internal isolated-code readiness decisions**, not branch merges, staging deployment, approved commercial policy, live payouts or launch.

**Preserved:** #101 existing INTERNAL_READY=1, #102 prior QA_PASS, #103 existing status unchanged. The separate `docs/HQ_160_A_STATUS_20261031.md` on #112's stacked branch remains an earlier snapshot and must not be treated as the latest decision.

| Task | Product PR / exact product SHA | B QA-only PR / SHA / successful CI runs | Full original contract decision | Remaining blocker or safe boundary |
| --- | --- | --- | --- | --- |
| #104 | #166 `148b074f60b91c3bb13ec4a0d6f4e0f0f44a3075` | #179 `24dfcaf35d42984e90c6407d3dd07fa4553e3f15`; 41187465864 / 41187465841 | **HOLD / INTERNAL_READY=0** | Original asks to *decide* reward accrual/confirmation timing. Three hypothetical timings pass QA but no approved selection, actual refund rule or trusted settlement evidence. Separate review UI follow-on in this PR is **QA_PENDING**, not part of B's previous exact-SHA approval. |
| #105 | #170 `97d3aa8e8a707363657e86b7b643b653df1e285e` | #186 `e9625f097ef92f5cd505639dae7f6507aa0f614d`; 41188521537 / 41188521503 | **HOLD / INTERNAL_READY=0** | Original asks to set repeat/other-tutor/monthly-renewal benefit conditions. A/B/C are simulation candidates only, no chosen period/limits, approval or linked trusted booking history. |
| #106 | #171 `9493f60b38585ec58c6ea05781015d5e70bd73b8` | #187 `5d41c30ad475cbde42e59681eb10af4d2158825a`; 41188550189 / 41188550215 | **INTERNAL_READY=1 — A APPROVED, original review-proposal scope** | Original explicitly asks for a *representative review proposal* comparing discounts/points/cash, stacking, expiry and caps. Three bounded comparison candidates, documented 30/90-day assumptions, 15 original tests, 8 B adversarial tests and both independent CI runs satisfy **that review deliverable**. No incentive policy, credit or cash payout is approved. #104/#105 final policy choices are not prerequisites for a standalone comparative proposal. |
| #107 | #175 `6bd504aa2de66d18e041a7691fd5505812c9319b` | #180 `3374e8be145b7083be500b4f6d4798b2da60b051`; 41187496317 / 41187496346 | **HOLD / INTERNAL_READY=0** | Country-specific legal/tax determination and permitted multi-level structure require actual external review. Read-only compliance UI and fail-closed gate are B QA_PASS subcomponents, never legal authorization. |
| #108 | #177 `7cacebac90ebdc350333659326417fc3678d96ec` | #185 `6803917bff8bc9130e496aceb0fb62c78c7aae0c`; 41188486306 / 41188486320 | **INTERNAL_READY=1 — A APPROVED, isolated referral-link/relationship contract** | Original asks to store referral code/link/relationship and enforce duplicate/existing-member/immutable-parent rules. Actual authenticated HTTP + SQLite persistence, signup prefill, replay/self/cycle/role rejection, UI and independent B QA satisfy this scope. Depends on existing #101 relationship model, **not** #107 legal payout approval: no rewards/financial authorization. Not deployed. |
| #109 | #178 `8e04ee874b1b6b3649080d833d5f813308c07a66` | #183 `72f2cb7a69e152b5cd234d167a4a37be75935dc1`; 41188444196 / 41188444208 | **HOLD / INTERNAL_READY=0** | Trusted-input risk scoring QA_PASS, but no server booking/identity evidence adapter and no integrated prevention/detection for fake trades or multi-account abuse; module-only review cannot meet original end-to-end detection contract. |

## A approval effect

**New INTERNAL_READY decisions: +2 (#106, #108).** Both have unchanged exact product SHA, explicit independent B QA_PASS and original-contract comparison. This is a verified internal scope decision only; no main merge, staging deployment, policy approval, actual money or payout. #101 previous INTERNAL_READY remains preserved. #104/#105/#107/#109 remain full-contract HOLD, with scoped B QA_PASS tracked separately.

## New safe product work (separate follow-on, NOT READY)

A has started a standalone read-only #104 review page `phase3/reward-timing-review.html`, its regression tests `phase3/test_task104_review_page.py`, static allowlist and platform navigation. It explains three hypothetical trigger times, refund and pending refund safeguards, unresolved policy decisions and a manual review checklist. No API, scripts, payments, data writes or policy authorization. This new PR must receive **its own exact-head CI and B independent QA**. Original #104 SHA QA_PASS is not reused as QA for this follow-on. The UI is not deployed to any test URL.

## Next work

1. B independent QA of this new follow-on exact HEAD; fix failures without bypassing B.
2. #104 policy decision remains blocked pending actual policy choice; no invented legal/financial rule.
3. #107 legal/tax decisions remain external; preserve safe read-only UI. #109 needs trusted server booking/identity adapter and independent end-to-end abuse QA.
4. Prepare isolated preview only via an already authorized safe deployment path after DB backup/restore and provenance checks. Do not touch TEST99 or production without meeting existing deployment gates.

**Evidence anchors:** GitHub Issue #34 B/15 comments #6541573156 and #6541669803; product PRs #166/#170/#171/#175/#177/#178; QA-only PRs #179/#180/#183/#185/#186/#187. B QA_PASS ≠ A INTERNAL_READY ≠ deployment.
