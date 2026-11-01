"""#123 follow-on: atomic SQLite + HMAC-signed SIMULATOR event intake.

This is a review-only local adapter. HMAC proves only possession of the
explicit test key; it does NOT authenticate a real payment provider.
Never connects to production DB, processes real payments, or calls a gateway.
"""
import hashlib
import hmac
import json
import re
import sqlite3

from team14_payment_booking_projection import reconcile_payment_booking

_SIGNATURE = re.compile(r"sha256=([0-9a-f]{64})\\Z")
_REQUIRED_EVENT = frozenset({
    "source", "booking_id", "payment_id", "event_id", "sequence", "outcome"
})
_SOURCE = "TEST_SIGNED_PROVIDER_SIMULATOR"


def _pairs_unique(pairs):
    data = {}
    for key, value in pairs:
        if key in data:
            raise ValueError("duplicate JSON field")
        data[key] = value
    return data


def _verify_test_signature(payload, signature, test_key):
    if type(payload) is not bytes or not 0 < len(payload) <= 8192:
        raise ValueError("invalid event payload")
    if type(test_key) is not bytes or len(test_key) < 32:
        raise ValueError("invalid test signing key")
    if type(signature) is not str or not _SIGNATURE.fullmatch(signature):
        raise ValueError("invalid signature header")
    expected = hmac.new(test_key, payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature[7:]):
        raise ValueError("signature mismatch")


def initialize_review_db(connection):
    """Initialize only the caller-supplied isolated SQLite connection."""
    connection.executescript("""
        PRAGMA foreign_keys = ON;
        CREATE TABLE IF NOT EXISTS review_bookings (
          booking_id TEXT PRIMARY KEY,
          payment_id TEXT NOT NULL UNIQUE,
          lesson_count INTEGER NOT NULL CHECK(lesson_count BETWEEN 1 AND 1000),
          completed_lessons INTEGER NOT NULL CHECK(completed_lessons >= 0),
          payment_state TEXT NOT NULL DEFAULT 'PENDING',
          booking_state TEXT NOT NULL DEFAULT 'AWAITING_PAYMENT',
          remaining_bookable_lessons INTEGER NOT NULL DEFAULT 0,
          version INTEGER NOT NULL DEFAULT 0,
          CHECK(completed_lessons <= lesson_count)
        );
        CREATE TABLE IF NOT EXISTS review_payment_events (
          event_id TEXT PRIMARY KEY,
          payment_id TEXT NOT NULL REFERENCES review_bookings(payment_id),
          sequence INTEGER NOT NULL CHECK(sequence > 0),
          outcome TEXT NOT NULL,
          payload_digest TEXT NOT NULL,
          UNIQUE(payment_id, sequence)
        );
    """)


def seed_review_booking(connection, *, booking_id, payment_id,
                        lesson_count, completed_lessons=0):
    """Seed test-only data; never read or write operating reservation tables."""
    booking = dict(booking_id=booking_id, payment_id=payment_id,
                   lesson_count=lesson_count, completed_lessons=completed_lessons)
    projection = reconcile_payment_booking(booking=booking, events=[])
    connection.execute(
        "INSERT INTO review_bookings (booking_id, payment_id, lesson_count, "
        "completed_lessons, payment_state, booking_state, remaining_bookable_lessons) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (booking_id, payment_id, lesson_count, completed_lessons,
         projection["payment_state"], projection["booking_state"],
         projection["remaining_bookable_lessons"]))
    connection.commit()


def _load_review_booking(connection, booking_id):
    row = connection.execute(
        "SELECT booking_id, payment_id, lesson_count, completed_lessons "
        "FROM review_bookings WHERE booking_id = ?", (booking_id,)).fetchone()
    if row is None:
        raise ValueError("unknown booking")
    return dict(zip(("booking_id", "payment_id", "lesson_count",
                     "completed_lessons"), row))


def read_review_snapshot(connection, *, booking_id):
    """Read isolated review tables only; NOT an authenticated user endpoint."""
    row = connection.execute(
        "SELECT booking_id, payment_id, lesson_count, completed_lessons, "
        "payment_state, booking_state, remaining_bookable_lessons, version "
        "FROM review_bookings WHERE booking_id = ?", (booking_id,)).fetchone()
    if row is None:
        raise ValueError("unknown booking")
    keys = ("booking_id", "payment_id", "lesson_count", "completed_lessons",
            "payment_state", "booking_state", "remaining_bookable_lessons", "version")
    return dict(zip(keys, row))


def apply_test_signed_event(connection, *, payload, signature, test_key):
    """Verify local HMAC then atomically store an event and recalculate booking.

    Idempotent exact payload replay does not increment version. Conflicting
    event_id or sequence is rejected and rolled back, not silently replaced.
    A real provider signature/webhook and user-authenticated API are NOT present.
    """
    _verify_test_signature(payload, signature, test_key)
    try:
        data = json.loads(payload.decode("utf-8"), object_pairs_hook=_pairs_unique,
                          parse_constant=lambda x: (_ for _ in ()).throw(
                              ValueError("non-finite JSON number")))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid JSON payload") from exc
    if type(data) is not dict or set(data) != _REQUIRED_EVENT:
        raise ValueError("invalid event fields")
    if data["source"] != _SOURCE:
        raise ValueError("untrusted event source")
    event = {k: data[k] for k in ("event_id", "payment_id", "sequence", "outcome")}
    digest = hashlib.sha256(payload).hexdigest()

    connection.execute("BEGIN IMMEDIATE")
    try:
        booking = _load_review_booking(connection, data["booking_id"])
        if event["payment_id"] != booking["payment_id"]:
            raise ValueError("cross-booking payment mismatch")
        old = connection.execute(
            "SELECT payload_digest FROM review_payment_events WHERE event_id = ?",
            (event["event_id"],)).fetchone()
        if old is not None and old[0] != digest:
            raise ValueError("conflicting event_id replay")
        records = connection.execute(
            "SELECT event_id, payment_id, sequence, outcome "
            "FROM review_payment_events WHERE payment_id = ?",
            (booking["payment_id"],)).fetchall()
        events = [dict(zip(("event_id", "payment_id", "sequence", "outcome"), row))
                  for row in records]
        if old is None:
            events.append(event)
        projection = reconcile_payment_booking(booking=booking, events=events)
        if old is None:
            connection.execute(
                "INSERT INTO review_payment_events "
                "(event_id, payment_id, sequence, outcome, payload_digest) "
                "VALUES (?, ?, ?, ?, ?)",
                (event["event_id"], event["payment_id"], event["sequence"],
                 event["outcome"], digest))
            connection.execute(
                "UPDATE review_bookings SET payment_state = ?, booking_state = ?, "
                "remaining_bookable_lessons = ?, version = version + 1 "
                "WHERE booking_id = ?",
                (projection["payment_state"], projection["booking_state"],
                 projection["remaining_bookable_lessons"], booking["booking_id"]))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {
        "task": 123, "status": "SIGNED_SIMULATOR_SQLITE_REVIEW_ONLY",
        "simulator_signature_checked": True,
        "atomic_review_db_update": True,
        "idempotent_replay": old is not None,
        "projection": projection,
        "snapshot": read_review_snapshot(connection, booking_id=booking["booking_id"]),
        "payment_event_provenance_verified": False,
        "operating_db_connected": False,
        "production_booking_updated": False,
        "real_money_enabled": False,
        "provider_api_called": False,
        "authenticated_user_api_connected": False,
    }
