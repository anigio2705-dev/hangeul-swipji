"""#114 isolated per-transaction, four-bucket simulation ledger.

This is NOT a production accounting, payment, refund, credit or payout system.
Only trusted server adapters may supply verified transaction/evidence inputs.
No connection to the operating booking database or payment providers is made.
"""
import hashlib
import json
import re
import sqlite3

BUCKETS = ("teacher", "platform", "referral", "benefit")
MAX_KRW = 10**12
ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")


def _identifier(value, name):
    if type(value) is not str or not ID_PATTERN.fullmatch(value):
        raise ValueError("invalid " + name)
    return value


def _amount(value, name):
    if type(value) is not int or not 0 <= value <= MAX_KRW:
        raise ValueError("invalid " + name)
    return value


class SimulatedTransactionLedger:
    """Append-only SQLite test ledger; file path must be a test-isolated DB.

    Default is in-memory. Do NOT point this class at an operating database.
    A future production adapter requires separate auth, policy and legal gates.
    """

    def __init__(self, path=":memory:"):
        self.db = sqlite3.connect(path, isolation_level=None, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
CREATE TABLE IF NOT EXISTS sim_tx (
  tx_id TEXT PRIMARY KEY,
  evidence_id TEXT NOT NULL,
  gross_krw INTEGER NOT NULL CHECK(gross_krw > 0),
  request_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sim_entry (
  tx_id TEXT NOT NULL REFERENCES sim_tx(tx_id),
  bucket TEXT NOT NULL CHECK(bucket IN ('teacher','platform','referral','benefit')),
  amount_krw INTEGER NOT NULL CHECK(amount_krw >= 0),
  PRIMARY KEY(tx_id, bucket)
);
CREATE TRIGGER IF NOT EXISTS sim_tx_no_update BEFORE UPDATE ON sim_tx
BEGIN SELECT RAISE(ABORT, 'immutable simulation ledger'); END;
CREATE TRIGGER IF NOT EXISTS sim_tx_no_delete BEFORE DELETE ON sim_tx
BEGIN SELECT RAISE(ABORT, 'immutable simulation ledger'); END;
CREATE TRIGGER IF NOT EXISTS sim_entry_no_update BEFORE UPDATE ON sim_entry
BEGIN SELECT RAISE(ABORT, 'immutable simulation ledger'); END;
CREATE TRIGGER IF NOT EXISTS sim_entry_no_delete BEFORE DELETE ON sim_entry
BEGIN SELECT RAISE(ABORT, 'immutable simulation ledger'); END;
""")

    def close(self):
        self.db.close()

    def record(self, *, tx_id, evidence_id, gross_krw, teacher_krw,
               platform_krw, referral_krw, benefit_krw):
        _identifier(tx_id, "transaction id")
        _identifier(evidence_id, "trusted evidence id")
        gross = _amount(gross_krw, "gross_krw")
        if gross == 0:
            raise ValueError("gross must be positive")
        amounts = {
            "teacher": _amount(teacher_krw, "teacher_krw"),
            "platform": _amount(platform_krw, "platform_krw"),
            "referral": _amount(referral_krw, "referral_krw"),
            "benefit": _amount(benefit_krw, "benefit_krw"),
        }
        if sum(amounts.values()) != gross:
            raise ValueError("allocation must conserve gross KRW")
        payload = [tx_id, evidence_id, gross, *(amounts[k] for k in BUCKETS)]
        request_hash = hashlib.sha256(
            json.dumps(payload, separators=(",", ":")).encode("ascii")
        ).hexdigest()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            prior = self.db.execute(
                "SELECT request_hash FROM sim_tx WHERE tx_id=?", (tx_id,)
            ).fetchone()
            if prior is not None:
                if prior["request_hash"] != request_hash:
                    raise ValueError("transaction idempotency conflict")
            else:
                self.db.execute(
                    "INSERT INTO sim_tx VALUES(?,?,?,?)",
                    (tx_id, evidence_id, gross, request_hash)
                )
                self.db.executemany(
                    "INSERT INTO sim_entry VALUES(?,?,?)",
                    [(tx_id, bucket, amounts[bucket]) for bucket in BUCKETS]
                )
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return self.read(tx_id)

    def read(self, tx_id):
        _identifier(tx_id, "transaction id")
        row = self.db.execute(
            "SELECT tx_id,evidence_id,gross_krw FROM sim_tx WHERE tx_id=?",
            (tx_id,)
        ).fetchone()
        if row is None:
            raise KeyError("transaction not found")
        entries = {
            r["bucket"]: r["amount_krw"] for r in self.db.execute(
                "SELECT bucket,amount_krw FROM sim_entry WHERE tx_id=?",
                (tx_id,)
            )
        }
        if set(entries) != set(BUCKETS) or sum(entries.values()) != row["gross_krw"]:
            raise AssertionError("simulated transaction ledger invariant violated")
        return {
            "tx_id": row["tx_id"],
            "evidence_id": row["evidence_id"],
            "gross_krw": row["gross_krw"],
            "separate_ledger_entries": [
                {"bucket": bucket, "amount_krw": entries[bucket]}
                for bucket in BUCKETS
            ],
            "real_money": False,
            "policy_approved": False,
            "payment_enabled": False,
            "payout_authorized": False,
            "operating_db_connected": False,
        }
