# Team13 — 8th directive evidence ledger (2026-10-28)

Scope: original backlog #21-30 and #71-100, total 40. Source: docs/platform-execution-backlog-20261027/docs/PLATFORM_EXECUTION_BACKLOG.md (read only). This is a team evidence report, not a modification to the master 160-item checklist.

## Latest verified automated baseline
Commit: c163038532e6aff1661dd36ca7c15ff4e4e8cb22
Actions: https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40613496099
Python: 88 tests, OK, 0 failures. Browser: 13 PASS messages, job success.
Automated browser Jitsi is MOCKED; physical two-device audio/video NOT VERIFIED.

## Per-number evidence and status
Classification: DEVELOPMENT_TEST_PASS means isolated automated checks exist but integration/approval remains. NEEDS_FIX means required implementation or integration is missing or not evidenced. EXTERNAL_HOLD means real-world/human/vendor/policy decision required. NO item marked COMPLETE.

| Number | Status | Evidence or gap |
|---|---|---|
|21|NEEDS_FIX|Home CTA test passes, but full public route not verified|
|22|DEVELOPMENT_TEST_PASS|Booked-class route and same mocked instant room tests; real two-device unverified|
|23|EXTERNAL_HOLD|Jitsi provider identity enforcement not demonstrated|
|24|NEEDS_FIX|Actual camera/mic error states not exhaustively tested|
|25|EXTERNAL_HOLD|Physical two-device audio/video not run|
|26|EXTERNAL_HOLD|PC/phone real video/audio and owner final verification|
|27|NEEDS_FIX|Device switching and reconnect not comprehensively tested|
|28|NEEDS_FIX|Waiting/expiry tested; provider outage/late arrival gaps|
|29|NEEDS_FIX|API ownership tested; leaked Jitsi link external access risk|
|30|NEEDS_FIX|Mocked vs real evidence distinction documented; full session evidence absent|
|71|NEEDS_FIX|Teaching application-to-publication flow not integrated|
|72|NEEDS_FIX|Legacy teacher profile fields exist; full editing verification missing|
|73|NEEDS_FIX|Common teaching-profile approval mapping not integrated|
|74|NEEDS_FIX|Single/monthly lesson condition UI missing evidence|
|75|NEEDS_FIX|Teacher operating guide not fully verified|
|76|NEEDS_FIX|Legacy slots exist; leave/change/conflict lifecycle not verified|
|77|NEEDS_FIX|No verified unbounded/paginated recruitment|
|78|NEEDS_FIX|Approval rejection/review reasons not integrated|
|79|NEEDS_FIX|Teacher dashboard full booking/completion/accrual integration absent|
|80|NEEDS_FIX|Provider exit with bookings unresolved|
|81|NEEDS_FIX|Learner preference selection not integrated|
|82|NEEDS_FIX|Provider search exists in legacy code; multi-criteria integration unverified|
|83|NEEDS_FIX|Result detail/verified credentials not fully verified|
|84|NEEDS_FIX|DST/timezone edge testing missing|
|85|NEEDS_FIX|Beginner recommendation guidance missing evidence|
|86|NEEDS_FIX|Free/paid scope and lesson preview unverified|
|87|NEEDS_FIX|No-match fallback notification not integrated|
|88|NEEDS_FIX|Inquiry/report/privacy/block policy incomplete|
|89|EXTERNAL_HOLD|Ranking fairness policy needs HQ decision|
|90|EXTERNAL_HOLD|Consent and scoped sharing policy needs HQ decision|
|91|EXTERNAL_HOLD|One-off/monthly commercial terms need HQ/owner approval|
|92|NEEDS_FIX|Pre-booking confirmation screen not verified|
|93|DEVELOPMENT_TEST_PASS|Legacy slot uniqueness and concurrency checks in existing tests; cross-team monthly integration outstanding|
|94|NEEDS_FIX|Pure monthly event envelope added; no persistent monthly booking linkage|
|95|NEEDS_FIX|Recurring reschedule/holiday handling incomplete|
|96|NEEDS_FIX|Booking notifications unverified|
|97|NEEDS_FIX|Booking lesson/unit snapshot exists; full screen flow unverified|
|98|NEEDS_FIX|Attendance records exist; real lesson delivery not proven|
|99|NEEDS_FIX|Homework/feedback endpoints exist; full next-booking flow unverified|
|100|NEEDS_FIX|Mid-month teacher transfer/cancellation lifecycle incomplete|

Counts: COMPLETE 0; DEVELOPMENT_TEST_PASS 2; NEEDS_FIX 32; EXTERNAL_HOLD 6; NOT_STARTED 0. Statuses are conservative; code existence alone is not completion.

## Cross-team contract boundaries
Team11 contract at 183a318e6600a2be8835943f067fe7c3d6ac8fa8: phase3/common_contract.py uses multi-role pure validators and approval states; legacy users.role and users.approved remain single-value. No unauthorized schema migration.
Team14 contract at ab05d827c2d5ba847bcc2dcd06922640846c126b: phase3/team14_monthly_sim.py uses Month.complete(index, operation_id) with isolated in-memory ledger. Team13 transaction_event_contract emits monthId, lessonIndex, eventId, bookingId, type, paymentExecuted=False. Real authenticated durable event delivery and deduplication NOT IMPLEMENTED.

## HQ approval request
Department: Team13 platform.
Request: confirm canonical multi-role/teaching approval identity mapping, ownership of shared server/schema integration, and monthly course booking identifiers; authorize a serial cross-team integration window only after Team11/14 contracts approved.
Reason: safely connect booking and completion events without rewriting instant matching or mutating other teams' branches.
Risk: premature integration can grant unapproved teaching access, double-book, or duplicate simulated settlement.
If not approved: keep integration HOLD; continue isolated tests and read-only work.
Recommendation: HQ first locks shared role/approval/error-code contract and monthly session identity/idempotency; Team13 then implements on its own branch with security regressions. Owner-level real video, deployment, money and pricing remain HOLD.

No merge, deployment, real payments, or live video verification performed.
