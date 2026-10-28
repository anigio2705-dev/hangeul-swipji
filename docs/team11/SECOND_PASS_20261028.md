# Team11 second-pass compatibility and API contract report — 2026-10-28

Branch: team11/common-foundation-20261028. No integration, deployment, or database migration.

## Scope verified
Existing phase3/schema.sql stores one users.role (learner|partner|teacher|admin), users.approved, bookings with learner_id/teacher_id, and append-only ledger. instant_matching.py has queue/match states offered|active|ended and response states idle|waiting. The previous common_contract.py checks IDs, roles, approval, self-referral, nonnegative integer minor-unit amounts; it does not implement database authorization, anti-cycle referral traversal, payment idempotency or state transitions.

## Added
- phase3/common_contract.py: read-only roles_from_legacy and lossless-only legacy_role_for. A multi-role account cannot be written into legacy users.role without an explicit migration. Added candidate state and error enums.
- phase3/test_common_compatibility.py: 8 isolated test methods covering legacy round-trip, privilege non-escalation, multi-role rejection, invalid legacy roles, booking/match/transaction states, invalid states, error codes and ID/money boundaries.
- Existing phase3/test_common_contract.py: 7 test methods remain unchanged.

## Candidate contract for teams 13 and 14
IDs: opaque ASCII letters/digits/_/- up to 128 characters in new contract only; legacy IDs must be checked before adopting this rule. user_id, booking_id, slot_id, match_id, transaction_id, refund_id, referral_edge_id are separate namespaces; never accept client-supplied ownership claims.
Booking states: reserved, expired, cancelled, test_paid, in_class, completed, refunded (candidate vocabulary; confirm against all server paths).
Match states: idle, waiting, offered, active, ended. idle/waiting are API view states, not database row states.
Transaction states: pending, authorized, captured, failed, refunded, partially_refunded. Candidate only; existing mock payment statuses must be mapped explicitly.
Error envelope candidate: {error:{code,message,requestId}}. Codes UNAUTHENTICATED=401, FORBIDDEN=403, NOT_FOUND=404, VALIDATION_ERROR=400, CONFLICT=409, INVALID_STATE=409. Existing server errors are not yet converted.
Amounts: integer minor units, ISO currency required at API boundary, idempotency key required for financial writes, no floats. Currency-specific minor-unit conversion requires separate validation.
Do not infer a valid transition from enum membership. Each domain team must propose transition tables and negative tests; financial state is not a booking state.

## Risks / gates
Legacy single-role users cannot simultaneously teach and learn under the old schema. Read-only projection does not solve persistence. A multi-role migration needs staged compatibility reads, authorization review and rollback. Do not update phase3/schema.sql, server.py, instant_matching.py, payments.py, or operational DB in this team branch.
No payout percentage/depth/eligibility is set. Referral cycles, refund conservation, payment replay, permissions and cross-role booking conflicts remain integration-test gaps.
Test execution must be independently verified; committing tests does not constitute a passing run.
HQ decisions: identity source, multi-role migration design, final status mappings, DB vendor, approval policy, legal referral policy, shared-file integration order.

## Execution evidence (isolated reconstruction, not repository checkout)
2026-10-28: Direct git clone from execution container failed because github.com DNS resolution was unavailable. Reconstructed the fetched common_contract.py validator logic and the 15 test method scenarios in a temporary isolated Python directory; executed python3 -m unittest discover -s <temporary directory> -p 'test_*.py' -v. Result: Ran 15 tests, OK, exit code 0. This verifies the reconstructed logic only, NOT an exact GitHub file checkout or complete phase3 regression. The unrelated notebook spreadsheet warmup emitted an error before the subprocess, but unittest exited 0. Next action: run the exact checked-out files and full suite in GitHub CI or a network-enabled workspace; attach workflow run URL and SHA. No live DB, production service or deployment was touched.
