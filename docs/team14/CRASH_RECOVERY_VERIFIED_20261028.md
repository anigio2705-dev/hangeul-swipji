# Team14 simulated settlement crash recovery — 2026-10-28

## Implemented
- `phase3/team14_persistent.py`: failure injection hook in atomic SQLite ledger and before operation commit. Ledger rollback proven.
- `phase3/team14_recovery.py`: durable `recovery_events` with prepared/settled states, event ID/payload signature conflict detection, trusted callback revalidation and recovery replay.
- `phase3/team14_instant_verified_bridge.py`: verified Team13 instant completion now enters durable recoverable coordinator; no public payment endpoint.
- `phase3/team14_refund_workflow.py`: refund_requests state machine requested -> approved/rejected/cancelled; approved -> applied with same-connection atomic refund reversals and operation marker. Only booking learner can request; internal test reviewer applies decision.
- `phase3/test_team14_crash_recovery.py`: 3 test methods covering 9 settlement injection checkpoints, 5 refund posting checkpoints, restart/idempotency/terminal decisions.
- `.github/workflows/team14-monthly-tests.yml`: existing suites preserved, new crash tests included.

## Verified GitHub Actions
- **PASS**: https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40635024934
- Commit `b8335ee9cfb3b9395dbe3a63222680961d6e539e`
- 152/152 tests passed: previous 149 plus 3 crash recovery tests. No test criteria were relaxed.

## Fault matrix
- Event received: recovery journal is prepared; replay after restart succeeds.
- Before ledger: settlement transaction rolls back; replay succeeds.
- After teacher / referral / platform accrual entries: ledger transactions roll back atomically; replay succeeds.
- Before settlement operation commit: rollback and replay succeed.
- After referral award / before settled marker: durable replay preserves single referral award, ledger and final state.
- Refund reversal / teacher reversal / referral reversal / platform reversal / before refund commit: same-file SQLite rollback, approved refund remains pending; retry applies exactly once.
- After DB restart, same event and approved refund return persisted results without additional accrual/reversal entries.
- Rejected/cancelled refund requests cannot be paid or reapproved.

## Safety and current limitations
- Simulation only. The upstream Team13 evidence is a virtual session and does not establish real media transmission or duration. No payout, charge or real refund API.
- Multiple SQLite files remain (Team13 event server DB, Team14 settlement DB, Team14 referral DB). This design is **replay-recoverable, not a single atomic distributed commit**. Exactly-once real-money settlement is NOT asserted.
- Pending recovery requires execution of `recover_prepared` with trusted up-to-date server-side resolvers. There is no automatic background process or cross-team wiring of Team13 outbox acknowledgement.
- Refund workflow is internal-only; `test_reviewer` is a simulation-only authorization placeholder, not a production authorization model.
- Applied refund reduces referral allocation in the ledger through `referral_reversal` but the separate `referral_awards` JSON remains historical gross award. Recipient-level adjustment records and outbox delivery receipts are not implemented; do not treat awards as payable balances.
- A process crash or lost event after Team13 acknowledgement but before Team14 preparation may require Team13 producer redelivery. The real delivery atomicity and escalation need Team13/15 integrated tests.

## Coordination
13: preserve eventId/bookingId/learnerId/teacherId/amount/type/status and server-only verified_event_for_team14; expose non-acknowledged retry list or stable event ID replay for recovery, never trust client flags.
15: invoke recovery on restart within trusted staging process; exercise event outbox acknowledgement failures and full E2E; do not merge to main.
