# Team13 → Team14 durable outbox handoff (2026-10-28)

## Verified source
Read **only** `instant_matching.verified_outbox_envelope(db, event_id)` through a trusted server-side integration. Do not trust browser-provided event bodies, flags, prices, or timestamps.

Envelope version 1 fields: `version=1`, `eventId`, `bookingId`, `learnerId`, `teacherId`, `amount` (KRW), `currency="KRW"`, `completedAt` (server Unix epoch seconds), `type`, `bookingStatus`, `deliveryStatus` (`pending` or `acknowledged`), `attempts`, `receiptId`, `paymentExecuted=false`, `verifiedByServer=true`.

The envelope is derived from the SQLite event row, approved teacher, and current booking state; changing those values causes validation failure. `pending_settlement_events` is a **read-only** fetch and never confirms delivery.

## Independent Team14 store: required protocol
1. Team14 maintains its own authenticated mapping from the server booking to `month_id`, `lesson_id`, `transaction_id`, and `action` in its persistent business store; do **not** invent this data in Team13 or accept it from the client.
2. Team14 calls its own verified event consumer and persists the ledger transaction with a **unique, stable** `eventId` replay key. On repeated requests, return the **same** durable receipt without another posting.
3. Team13 MUST NOT mark an event acknowledged merely because it was read or an HTTP response arrived. After ledger commit, Team14 supplies the durable receipt through the trusted `confirm_settlement_receipt(db,event_id,"team14",receipt_id,settlement_confirmed=True)` API.
4. If the Team14 commit succeeds but the confirmation response is lost, the Team13 event remains pending; retry by `eventId`; Team14 deduplicates and returns the earlier receipt. Then confirm locally.
5. Acknowledge inserts into `instant_event_deliveries`; conflicting receipts raise HTTP 409. **Different DBs do not share a SQLite transaction**; this is at-least-once delivery + idempotent downstream processing, not an atomic two-DB commit.
6. On startup, call `pending_settlement_events` to resume; do not clear pending rows on shutdown.

## Distinct semantics
`deliveryStatus=acknowledged` means a downstream durable receipt has been confirmed, not real payment or transfer. All transactions are simulated only. `paymentExecuted=false` remains mandatory.

## Verification
`phase3/test_instant_matching.py` includes actual HTTP/SQLite event generation, duplicate attempts, restart/re-read, lost-response simulation, payload tampering, and revoked teacher tests. The lost-response consumer is a **fake durable receipt store**; Team14 and Team15 must still run cross-DB restart/ledger verification.

GitHub Actions run: https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40634853956
