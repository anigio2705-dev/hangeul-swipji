"""#124: isolated mock webhook signature, replay, ordering and missing-event inbox.

No provider integration, booking mutation, payment, payout or operating DB access.
A real provider adapter MUST separately define its signature format, timestamp
freshness, key rotation, authorized booking mapping and reconciliation contract.
"""
import hashlib
import hmac
import json
import re
import sqlite3

_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_STATUSES = frozenset({"pending", "succeeded", "failed", "canceled", "timed_out"})
_FIELDS = frozenset({"event_id", "booking_id", "sequence", "status"})


def sign_fixture(secret, payload):
    """Test-only signature fixture; not a real payment-provider protocol."""
    if not isinstance(secret, bytes) or len(secret) < 16:
        raise ValueError("test secret must be at least 16 bytes")
    if not isinstance(payload, bytes):
        raise ValueError("payload must be bytes")
    return "sha256=" + hmac.new(secret, payload, hashlib.sha256).hexdigest()


def _parse_verified(raw, signature, secret):
    if not isinstance(raw, bytes) or len(raw) > 4096:
        raise ValueError("invalid event bytes")
    expected = sign_fixture(secret, raw)
    if not isinstance(signature, str) or not hmac.compare_digest(signature, expected):
        raise ValueError("signature rejected")
    def reject_duplicate_members(pairs):
        item = {}
        for name, value in pairs:
            if name in item:
                raise ValueError("duplicate JSON member")
            item[name] = value
        return item

    try:
        item = json.loads(raw.decode("utf-8"),
                          object_pairs_hook=reject_duplicate_members)
    except (UnicodeError, ValueError) as exc:
        raise ValueError("invalid event JSON") from exc
    if not isinstance(item, dict) or set(item) != _FIELDS:
        raise ValueError("invalid event schema")
    for field in ("event_id", "booking_id"):
        if not isinstance(item[field], str) or not _ID.fullmatch(item[field]):
            raise ValueError("invalid " + field)
    if type(item["sequence"]) is not int or not 1 <= item["sequence"] <= 1000000:
        raise ValueError("invalid sequence")
    if not isinstance(item["status"], str) or item["status"] not in _STATUSES:
        raise ValueError("invalid status")
    return item


class MockWebhookInbox:
    """Atomic SQLite event inbox. Isolated test database ONLY."""

    def __init__(self, path, test_secret):
        if not isinstance(test_secret, bytes) or len(test_secret) < 16:
            raise ValueError("invalid test secret")
        self.secret = test_secret
        self.db = sqlite3.connect(path, timeout=5)
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS mock_events (
            event_id TEXT PRIMARY KEY, booking_id TEXT NOT NULL,
            sequence INTEGER NOT NULL, status TEXT NOT NULL,
            digest TEXT NOT NULL, applied INTEGER NOT NULL DEFAULT 0,
            UNIQUE(booking_id, sequence))""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS mock_bookings (
            booking_id TEXT PRIMARY KEY, sequence INTEGER NOT NULL,
            status TEXT NOT NULL)""")
        self.db.commit()

    def close(self):
        self.db.close()

    def _drain(self, booking_id):
        row = self.db.execute(
            "SELECT sequence FROM mock_bookings WHERE booking_id=?",
            (booking_id,)).fetchone()
        sequence = row[0] if row else 0
        applied = 0
        while True:
            event = self.db.execute(
                "SELECT event_id,status FROM mock_events WHERE booking_id=? "
                "AND sequence=? AND applied=0",
                (booking_id, sequence + 1)).fetchone()
            if event is None:
                break
            sequence += 1
            self.db.execute("UPDATE mock_events SET applied=1 WHERE event_id=?",
                            (event[0],))
            self.db.execute(
                "INSERT INTO mock_bookings(booking_id,sequence,status) "
                "VALUES(?,?,?) ON CONFLICT(booking_id) DO UPDATE SET "
                "sequence=excluded.sequence,status=excluded.status",
                (booking_id, sequence, event[1]))
            applied += 1
        return applied

    def ingest(self, raw, signature):
        item = _parse_verified(raw, signature, self.secret)
        digest = hashlib.sha256(raw).hexdigest()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            existing = self.db.execute(
                "SELECT digest FROM mock_events WHERE event_id=?",
                (item["event_id"],)).fetchone()
            if existing:
                if existing[0] != digest:
                    raise ValueError("event id reused with different payload")
                result = {"result": "DUPLICATE", "applied": 0}
            else:
                previous = self.db.execute(
                    "SELECT sequence FROM mock_bookings WHERE booking_id=?",
                    (item["booking_id"],)).fetchone()
                if previous and item["sequence"] <= previous[0]:
                    raise ValueError("stale sequence")
                try:
                    self.db.execute(
                        "INSERT INTO mock_events(event_id,booking_id,sequence,status,digest) "
                        "VALUES(?,?,?,?,?)",
                        (item["event_id"], item["booking_id"], item["sequence"],
                         item["status"], digest))
                except sqlite3.IntegrityError as exc:
                    raise ValueError("conflicting event sequence") from exc
                applied = self._drain(item["booking_id"])
                result = {"result": "APPLIED" if applied else "WAIT_MISSING",
                          "applied": applied}
            self.db.commit()
            return result
        except Exception:
            self.db.rollback()
            raise

    def reprocess(self, booking_id):
        """Retry queued events and expose next missing sequence for reconciliation."""
        if not isinstance(booking_id, str) or not _ID.fullmatch(booking_id):
            raise ValueError("invalid booking id")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            applied = self._drain(booking_id)
            row = self.db.execute(
                "SELECT sequence FROM mock_bookings WHERE booking_id=?",
                (booking_id,)).fetchone()
            last = row[0] if row else 0
            pending = self.db.execute(
                "SELECT COUNT(*) FROM mock_events WHERE booking_id=? AND applied=0",
                (booking_id,)).fetchone()[0]
            self.db.commit()
            return {"applied": applied, "pending": pending,
                    "next_expected_sequence": last + 1}
        except Exception:
            self.db.rollback()
            raise

    def snapshot(self, booking_id):
        if not isinstance(booking_id, str) or not _ID.fullmatch(booking_id):
            raise ValueError("invalid booking id")
        row = self.db.execute(
            "SELECT sequence,status FROM mock_bookings WHERE booking_id=?",
            (booking_id,)).fetchone()
        return None if row is None else {"sequence": row[0], "status": row[1]}
