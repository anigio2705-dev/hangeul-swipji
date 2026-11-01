"""#110 local Phase3 session/booking-backed participant explanation (review only).

This internal adapter resolves the actor from a stored hashed session and the
participant roster from SQLite. It never accepts browser-provided actor IDs,
rosters, policy signatures or evidence booleans. There is no HTTP endpoint,
approved policy, verified provider payment or operating DB connection here.
"""
import hashlib
import math
import re
import sqlite3

from team14_referral_participant_view import project_participant_view
from team14_referral_policy_preview import MAX_KRW, MAX_TIME, simulate_versioned_reward

_TOKEN = re.compile(r"[A-Za-z0-9_-]{8,256}\Z")
_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_ALLOWED_STATES = frozenset({
    "reserved", "test_paid", "in_class", "completed", "test_settled",
    "cancelled", "refunded", "expired",
})
_NO_REFERRER = "internal_no_referrer"
_PLATFORM = "internal_platform"


def authenticated_local_referral_view(db, *, session_token, booking_id, now):
    """Return only the session owner's nonbinding explanation.

    `db` must be the server-owned local Phase3 test connection. The caller
    must extract the cookie on the server, never from a client JSON field.
    The existence of a booking is not proof of actual provider payment.
    """
    if not isinstance(db, sqlite3.Connection):
        raise ValueError("server-owned SQLite connection required")
    if type(session_token) is not str or not _TOKEN.fullmatch(session_token):
        raise PermissionError("valid local session required")
    if type(booking_id) is not str or not _ID.fullmatch(booking_id):
        raise ValueError("invalid booking identifier")
    if type(now) not in (int, float) or not math.isfinite(now) or not 0 <= now <= MAX_TIME:
        raise ValueError("invalid server clock")

    token_hash = hashlib.sha256(session_token.encode("ascii")).hexdigest()
    actor = db.execute(
        "SELECT u.id,u.role,u.approved FROM sessions s "
        "JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>?",
        (token_hash, now),
    ).fetchone()
    if actor is None:
        raise PermissionError("unauthenticated or expired session")
    actor_id, actor_role, actor_approved = tuple(actor)

    booking = db.execute(
        "SELECT b.learner_id,b.teacher_id,b.referrer_id,b.price,b.status,"
        "s.teacher_id FROM bookings b "
        "LEFT JOIN slots s ON s.id=b.slot_id WHERE b.id=?", (booking_id,),
    ).fetchone()
    if booking is None:
        raise PermissionError("booking is unavailable")
    learner, teacher, referrer, price, state, slot_teacher = tuple(booking)
    # The booking and its server-owned slot must agree on the teacher.
    # Otherwise a modified booking row could authorize an unrelated teacher.
    if type(slot_teacher) is not str or slot_teacher != teacher:
        raise PermissionError("booking and slot teacher mismatch")
    if (not all(type(v) is str and _ID.fullmatch(v) for v in (learner, teacher))
            or learner == teacher or type(price) is not int
            or not 0 <= price <= MAX_KRW or state not in _ALLOWED_STATES):
        raise PermissionError("invalid trusted booking")
    if referrer is not None and (type(referrer) is not str
                                or not _ID.fullmatch(referrer)
                                or referrer in (learner, teacher)):
        raise PermissionError("invalid referral relationship")

    linked = db.execute(
        "SELECT referred_by FROM users WHERE id=?", (learner,)
    ).fetchone()
    if linked is None or (referrer is not None and linked[0] != referrer):
        raise PermissionError("referral relationship mismatch")

    # No arbitrary actor role or roster is accepted from the caller. A
    # platform view belongs only to the currently authenticated admin.
    if actor_role == "admin":
        role = "platform"
    elif actor_id == learner and actor_role == "learner":
        role = "learner"
    elif actor_id == teacher and actor_role in ("teacher", "partner") and actor_approved == 1:
        role = "teacher"
    elif actor_id == referrer and actor_role in ("learner", "teacher", "partner"):
        if actor_role in ("teacher", "partner") and actor_approved != 1:
            raise PermissionError("revoked referrer")
        role = "referrer"
    else:
        raise PermissionError("actor is not a booking participant")

    roster = {
        "learner": learner,
        "teacher": teacher,
        "referrer": referrer if referrer is not None else _NO_REFERRER,
        "platform": actor_id if role == "platform" else _PLATFORM,
    }
    if len(set(roster.values())) != 4:
        raise PermissionError("ambiguous participant roster")

    # No approved business policy exists. Never pass a fixture signing key,
    # client boolean, mock provider evidence or hypothetical payout into an
    # authenticated UI. The visible result is POLICY_UNVERIFIED / no amount.
    simulation = simulate_versioned_reward(
        policy_version="unapproved-review-only", gross_krw=price,
        payment_verified=False, lesson_completed=False,
        attendance_verified=False, refunded=False,
        referrer_eligible=False, as_of=int(now),
    )
    view = project_participant_view(
        simulation=simulation, role=role, authenticated_actor_id=actor_id,
        trusted_roster=roster, booking_evidence_verified=True,
    )
    if view["state"] != "POLICY_UNVERIFIED" or view["hypothetical_candidate_krw"] is not None:
        raise AssertionError("unapproved policy must never display a reward")
    return {
        **view,
        "source": "local_phase3_test_sqlite",
        "session_authenticated": True,
        "provider_payment_verified": False,
        "business_policy_approved": False,
        "production_session_verified": False,
        "original_contract_ready": False,
    }
