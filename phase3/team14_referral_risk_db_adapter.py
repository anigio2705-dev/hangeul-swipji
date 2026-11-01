"""#109 read-only trusted-evidence adapter for the *local Phase3 test SQLite*.

The caller passes a server-owned sqlite3.Connection, not request JSON.  The
adapter does not prove real identity, payment, or provider settlement.  All
outputs are REVIEW_ONLY; no reward, DB write, or real-money side effects.
"""
import sqlite3
import math


def _finite_time(value):
    return type(value) in (int, float) and math.isfinite(value)

from team14_persistent import SimError, ident
from team14_referral_risk import MAX_EDGES, screen_referral_risk


def screen_phase3_referral_evidence(db, *, referred_id, inviter_id, booking_id=None):
    """Read actual local test rows; fail closed when any evidence is absent.

    This is an internal server adapter, not a public HTTP endpoint. Never
    expose its account graph or review flags to arbitrary browser clients.
    """
    if not isinstance(db, sqlite3.Connection):
        raise SimError("VALIDATION_ERROR", "server-owned SQLite connection required")
    ident(referred_id)
    ident(inviter_id)
    if booking_id is not None:
        ident(booking_id)
    for user_id in (referred_id, inviter_id):
        if db.execute("SELECT 1 FROM users WHERE id=?", (user_id,)).fetchone() is None:
            raise SimError("NOT_FOUND", "referral account missing")

    # Bound the complete graph, not just the proposed edge. No client edges.
    edges = db.execute(
        "SELECT id,referred_by FROM users WHERE referred_by IS NOT NULL "
        "ORDER BY id LIMIT ?", (MAX_EDGES + 1,)
    ).fetchall()
    if len(edges) > MAX_EDGES:
        raise SimError("VALIDATION_ERROR", "referral graph exceeds review bound")
    stored_edges = [(row[0], row[1]) for row in edges]

    snapshot = None
    extra_flags = set()
    if booking_id is not None:
        booking = db.execute(
            "SELECT learner_id,teacher_id,status,referrer_id,price,created_at FROM bookings "
            "WHERE id=?", (booking_id,)
        ).fetchone()
        if booking is None:
            raise SimError("NOT_FOUND", "booking evidence missing")
        learner_id, teacher_id, status, booked_referrer, price, booking_at = tuple(booking)
        if booked_referrer != inviter_id:
            extra_flags.add("BOOKING_REFERRER_MISMATCH")
        # Test charge alone is not trusted provider evidence. Both a recorded
        # provider test event and the matching charge must exist.
        # Existence alone is not payment evidence: reject wrong amount, owner,
        # sign, timestamps, and contradictory provider event records. This is
        # STILL only locally simulated evidence, never actual settlement proof.
        charge_rows = db.execute(
            "SELECT amount,beneficiary,created_at FROM ledger "
            "WHERE booking_id=? AND kind='test_charge' LIMIT 2", (booking_id,)
        ).fetchall()
        test_charge = (
            len(charge_rows) == 1
            and type(price) is int and price > 0
            and type(charge_rows[0][0]) is int
            and charge_rows[0][0] == price
            and charge_rows[0][1] == learner_id
            and _finite_time(booking_at)
            and _finite_time(charge_rows[0][2])
            and charge_rows[0][2] >= booking_at
        )
        provider_rows = db.execute(
            "SELECT e.created_at,s.created_at FROM provider_events e "
            "JOIN payment_sessions s ON s.session_id=e.session_id "
            "AND s.booking_id=e.booking_id "
            "WHERE e.booking_id=? LIMIT 33", (booking_id,)
        ).fetchall()
        provider_event = (
            0 < len(provider_rows) <= 32
            and _finite_time(booking_at)
            and all(
                _finite_time(event_at) and _finite_time(session_at)
                and session_at >= booking_at and event_at >= session_at
                for event_at, session_at in provider_rows
            )
        )
        # A test charge cannot predate the payment session that is offered
        # as its supporting provider evidence.  No session means the existing
        # payment_verified conjunction remains false; do not invent proof.
        if test_charge and provider_rows:
            test_charge = all(
                _finite_time(session_at)
                and charge_rows[0][2] >= session_at
                for _event_at, session_at in provider_rows
            )
        if charge_rows and not test_charge:
            extra_flags.add("TEST_CHARGE_EVIDENCE_INVALID")
        attendees = {
            row[0] for row in db.execute(
                "SELECT user_id FROM attendance WHERE booking_id=? "
                "AND confirmed=1", (booking_id,)
            )
        }
        snapshot = {
            "student_id": learner_id,
            "teacher_id": teacher_id,
            "payment_verified": bool(test_charge and provider_event),
            "lesson_completed": status in ("completed", "test_settled"),
            "attendance_verified": {learner_id, teacher_id}.issubset(attendees),
        }
        if not provider_event:
            extra_flags.add("PROVIDER_TEST_EVIDENCE_MISSING")

    # There is no verified same-person/account-cluster source in this schema.
    # An empty cluster list is UNKNOWN, never an identity-clearance claim.
    result = screen_referral_risk(
        referred_id=referred_id, inviter_id=inviter_id,
        stored_edges=stored_edges, verified_account_clusters=(),
        booking=snapshot,
    )
    extra_flags.add("MULTI_ACCOUNT_IDENTITY_UNVERIFIED")
    result["flags"] = sorted(set(result["flags"]) | extra_flags)
    result["review_required"] = True
    result["account_identity_assessed"] = False
    result["source"] = "local_phase3_test_sqlite"
    result["source_verified_for_production"] = False
    result["actual_payment_verified"] = False
    result["decision"] = "REVIEW_ONLY"
    result["real_money"] = False
    result["payment_enabled"] = False
    result["reward_authorized"] = False
    result["policy_approved"] = False
    return result
