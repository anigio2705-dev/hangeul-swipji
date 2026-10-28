# Team14 — verified instant-event HTTP/SQLite settlement integration (2026-10-28)

## Scope & baseline
- Team11 SQLite schema and local server: `e39b9b0d20` (compatible phase3 schema).
- Team13 verified instant matching and `verified_event_for_team14`: `89e6ee0feec58b7fd1ca0f9da817447218eb94b2`.
- Team14 settlement/referral baseline: `d40b197a7c`.
- Integration PR #3: `680562a6186dbebbd4fae8ee72d5fed0eb410e34` (not merged).
- Branch: `team14/business-systems-audit-20261028`. No main/production deployment.

## Changed files and commits
1. `phase3/instant_matching.py` — imported pinned Team13 verified instant matching event/outbox code, retaining original matching path: `35a20142617f74f38bb81576953d946f8552267c`.
2. `phase3/team14_instant_verified_bridge.py` — internal-only verified completion consumption; real booking/role/price check, server-backed booking/lesson mapping, stable event and transaction IDs, simulated payout-ineligible flag; internal-only mock refund with participant authorization: `0ec2f16c1a4adae6643efc67ccee967608496efa`.
3. `phase3/test_team14_instant_http_settlement.py` — complete disposable-staging HTTP/SQLite journey and adversarial cases; commits `db2cfc9aedb347d4f07de20f2ed1a4e4cde193d7`, `a9cf68b5d536530ef2b12e47d57a954feaf7b708`, `5ca151c4abeafcc934209ae6f0d48764170acd82`.
4. `.github/workflows/team14-monthly-tests.yml` — compile, run all previous tests plus new HTTP journey: `29497f99287c0b0c9d6f180965b72188f127ab9c`.

## GitHub Actions verified
- [Latest run #40629166366](https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40629166366): **completed/success**, full log confirms **149 tests** across 17 test invocations; no failed tests.
- New end-to-end test file: 5/5 **PASS**; 3.922 seconds.
- [First integrated run #40629069420](https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40629069420): completed/success, initial 3/3 integrated checks.
- End-to-end path: HTTP signup -> instant queue/join -> both ready -> actual SQLite booking -> mutual session observe -> HTTP verified lesson completion -> Team13 server-only event verification -> Team14 mapped simulated settlement/referral ledger -> refund -> replay/double-refund guard -> close/reopen settlement/referral DB -> replay and balance persistence.

## Actual ledger / safety
- SQLite Team13: `users`, `bookings`, `instant_matches`, `instant_booking_links`, `instant_session_evidence`, `instant_lesson_events`.
- SQLite Team14: `months`, `lessons`, `operations` (idempotency), `ledger` (teacher/referral/platform accruals and reversal entries), `referral_links`, `referral_awards` (one award per lesson).
- Example tested: completion writes three accrual entries; full refund writes four adjustment entries and zeroes teacher/referral/platform balances. Partial refunds are additive; amount > remaining is blocked; same refund ID is idempotent; logs show recovery after DB reopen.
- All calculations are **illustrative unapproved policy** from existing Team14 code (20% commission and 3% referral), not approved operating conditions.
- No Stripe, external DB, payment, payout, actual refund, hosted deployment; result includes `real_money=False`, `payment_executed=False`, `payout_eligible=False`. Session-observe evidence is **simulated**, not proof of media or duration.

## Unfinished / risks
- Team13's `instant_event_deliveries` acknowledgement is not coupled atomically with Team14's two separate SQLite DBs. Durable Team14 operations/replay protect against duplicate ledger writes, but crash-safe cross-DB acknowledgement/outbox processing is still incomplete.
- Team13's cancellation event cannot be recorded after completion under existing one-completion-or-cancel design. Post-completion refunds currently use an internal trusted simulated adjustment, not a server-authenticated refund request endpoint or Team13 cancellation event. A refund policy/state workflow must be designed by 11/13/14 before use beyond tests.
- Team13 provider room URL is not an authenticated external media room and minimum real lesson duration has not been verified.
- No 15-team overall E2E success claim or 160-item completion claim. Existing 14-team tests and this HTTP+SQLite scoped journey passed.
