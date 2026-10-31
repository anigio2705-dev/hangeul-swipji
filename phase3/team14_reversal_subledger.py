"""#115: append-only simulated cancellation/refund reversal subledger.

Never connect this class to an operating database. Inputs must be supplied by a
future authenticated, policy-approved server adapter; no such adapter exists.
No actual refund, payment, transfer, recovery or payout is performed.
"""
import hashlib
import json

from team14_transaction_subledger import (
    BUCKETS, SimulatedTransactionLedger, _amount, _identifier,
)


def _target_buckets(original, gross, cumulative_refund):
    """Deterministic largest-remainder KRW allocation, stable bucket tie-break."""
    portions = {}
    remainders = []
    for index, bucket in enumerate(BUCKETS):
        quotient, remainder = divmod(original[bucket] * cumulative_refund, gross)
        portions[bucket] = quotient
        remainders.append((-remainder, index, bucket))
    missing = cumulative_refund - sum(portions.values())
    for _, _, bucket in sorted(remainders)[:missing]:
        portions[bucket] += 1
    return portions


class SimulatedReversalLedger(SimulatedTransactionLedger):
    """Isolated SQLite test-only ledger; original and reversal entries immutable."""

    def __init__(self, path=":memory:"):
        super().__init__(path)
        self.db.executescript("""
CREATE TABLE IF NOT EXISTS sim_reversal (
  reversal_id TEXT PRIMARY KEY,
  tx_id TEXT NOT NULL REFERENCES sim_tx(tx_id),
  evidence_id TEXT NOT NULL,
  event_kind TEXT NOT NULL CHECK(event_kind IN ('cancel','partial_refund','full_refund')),
  refund_krw INTEGER NOT NULL CHECK(refund_krw > 0),
  request_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sim_reversal_entry (
  reversal_id TEXT NOT NULL REFERENCES sim_reversal(reversal_id),
  bucket TEXT NOT NULL CHECK(bucket IN ('teacher','platform','referral','benefit')),
  reversed_krw INTEGER NOT NULL CHECK(reversed_krw >= 0),
  PRIMARY KEY(reversal_id,bucket)
);
CREATE TRIGGER IF NOT EXISTS sim_reversal_no_update BEFORE UPDATE ON sim_reversal
BEGIN SELECT RAISE(ABORT,'immutable simulated reversal'); END;
CREATE TRIGGER IF NOT EXISTS sim_reversal_no_delete BEFORE DELETE ON sim_reversal
BEGIN SELECT RAISE(ABORT,'immutable simulated reversal'); END;
CREATE TRIGGER IF NOT EXISTS sim_reversal_entry_no_update BEFORE UPDATE ON sim_reversal_entry
BEGIN SELECT RAISE(ABORT,'immutable simulated reversal'); END;
CREATE TRIGGER IF NOT EXISTS sim_reversal_entry_no_delete BEFORE DELETE ON sim_reversal_entry
BEGIN SELECT RAISE(ABORT,'immutable simulated reversal'); END;
""")

    def reverse(self, *, reversal_id, tx_id, evidence_id, event_kind, refund_krw):
        _identifier(reversal_id, "reversal id")
        _identifier(tx_id, "transaction id")
        _identifier(evidence_id, "trusted refund evidence id")
        if type(event_kind) is not str or event_kind not in (
                "cancel", "partial_refund", "full_refund"):
            raise ValueError("invalid event kind")
        amount = _amount(refund_krw, "refund_krw")
        if amount == 0:
            raise ValueError("refund must be positive")
        digest = hashlib.sha256(json.dumps(
            [reversal_id, tx_id, evidence_id, event_kind, amount],
            separators=(",", ":")).encode("ascii")).hexdigest()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            existing = self.db.execute(
                "SELECT request_hash FROM sim_reversal WHERE reversal_id=?",
                (reversal_id,)).fetchone()
            if existing is not None:
                if existing["request_hash"] != digest:
                    raise ValueError("reversal idempotency conflict")
            else:
                row = self.db.execute(
                    "SELECT gross_krw FROM sim_tx WHERE tx_id=?", (tx_id,)
                ).fetchone()
                if row is None:
                    raise KeyError("original transaction not found")
                gross = row["gross_krw"]
                refunded = self.db.execute(
                    "SELECT COALESCE(SUM(refund_krw),0) AS n "
                    "FROM sim_reversal WHERE tx_id=?", (tx_id,)
                ).fetchone()["n"]
                remaining = gross - refunded
                if amount > remaining:
                    raise ValueError("refund exceeds unrefunded transaction")
                if event_kind == "partial_refund" and amount >= remaining:
                    raise ValueError("partial refund must leave positive balance")
                if event_kind in ("cancel", "full_refund") and amount != remaining:
                    raise ValueError("full reversal must clear remaining balance")
                original = {
                    r["bucket"]: r["amount_krw"] for r in self.db.execute(
                        "SELECT bucket,amount_krw FROM sim_entry WHERE tx_id=?",
                        (tx_id,))
                }
                if set(original) != set(BUCKETS) or sum(original.values()) != gross:
                    raise AssertionError("original ledger invariant violated")
                # Allocate ONLY against the remaining, nonnegative bucket
                # balances. Subtracting independently rounded cumulative
                # targets can produce negative deltas after a partial refund.
                reversed_by_bucket = {
                    r["bucket"]: r["total"] for r in self.db.execute(
                        "SELECT e.bucket, SUM(e.reversed_krw) AS total "
                        "FROM sim_reversal_entry e "
                        "JOIN sim_reversal v ON v.reversal_id=e.reversal_id "
                        "WHERE v.tx_id=? GROUP BY e.bucket", (tx_id,))
                }
                balances = {
                    bucket: original[bucket] - reversed_by_bucket.get(bucket, 0)
                    for bucket in BUCKETS
                }
                if min(balances.values()) < 0 or sum(balances.values()) != remaining:
                    raise AssertionError("remaining bucket invariant violated")
                increments = _target_buckets(balances, remaining, amount)
                if min(increments.values()) < 0 or sum(increments.values()) != amount:
                    raise AssertionError("reversal conservation violated")
                if any(increments[b] > balances[b] for b in BUCKETS):
                    raise AssertionError("bucket over-reversal")
                self.db.execute(
                    "INSERT INTO sim_reversal VALUES(?,?,?,?,?,?)",
                    (reversal_id, tx_id, evidence_id, event_kind, amount, digest))
                self.db.executemany(
                    "INSERT INTO sim_reversal_entry VALUES(?,?,?)",
                    [(reversal_id, bucket, increments[bucket]) for bucket in BUCKETS])
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return self.read_reversal(reversal_id)

    def read_reversal(self, reversal_id):
        _identifier(reversal_id, "reversal id")
        row = self.db.execute(
            "SELECT reversal_id,tx_id,evidence_id,event_kind,refund_krw "
            "FROM sim_reversal WHERE reversal_id=?", (reversal_id,)
        ).fetchone()
        if row is None:
            raise KeyError("reversal not found")
        entries = {
            r["bucket"]: r["reversed_krw"] for r in self.db.execute(
                "SELECT bucket,reversed_krw FROM sim_reversal_entry "
                "WHERE reversal_id=?", (reversal_id,))
        }
        if set(entries) != set(BUCKETS) or sum(entries.values()) != row["refund_krw"]:
            raise AssertionError("reversal entry invariant violated")
        tx = self.read(row["tx_id"])
        cumulative = self.db.execute(
            "SELECT COALESCE(SUM(refund_krw),0) AS n "
            "FROM sim_reversal WHERE tx_id=?", (row["tx_id"],)
        ).fetchone()["n"]
        if cumulative > tx["gross_krw"]:
            raise AssertionError("over-reversal")
        return {
            "reversal_id": row["reversal_id"],
            "tx_id": row["tx_id"],
            "evidence_id": row["evidence_id"],
            "event_kind": row["event_kind"],
            "refund_krw": row["refund_krw"],
            "reversed_entries": [
                {"bucket": bucket, "amount_krw": entries[bucket]}
                for bucket in BUCKETS
            ],
            "cumulative_refunded_krw": cumulative,
            "remaining_krw": tx["gross_krw"] - cumulative,
            "real_money": False,
            "policy_approved": False,
            "payment_enabled": False,
            "refund_executed": False,
            "payout_authorized": False,
            "operating_db_connected": False,
        }
