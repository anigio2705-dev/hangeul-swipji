"""#123: isolated booking/payment/remaining-lessons projection.

Pure preview. NEVER a payment provider adapter, booking database update, or
authorization to schedule, refund, charge, or pay out. Callers MUST supply
authenticated provider and booking-owner evidence from a trusted server;
booleans in this function are fixtures, not authentication.
"""
import re

_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\\Z")
_KINDS = {"succeeded", "failed", "cancelled", "timed_out"}
_MAX_EVENTS = 100


def _id(value):
    return type(value) is str and _ID.fullmatch(value) is not None


def _lessons(value):
    return type(value) is int and 0 <= value <= 1000


def project_booking_payment(*, booking_id, purchased_lessons, consumed_lessons,
                            payment_events, trusted_provider_event_verified=False,
                            booking_owner_verified=False):
    """Return a deterministic read-only projection; never grant scheduling.

    Event schema: {id, booking_id, sequence, kind}; sequences are per booking.
    Missing sequence, replay, cross-booking or contradictory transitions HOLD.
    A late success after timeout/cancellation NEVER resurrects a booking.
    """
    if not _id(booking_id):
        raise ValueError("invalid booking id")
    if not _lessons(purchased_lessons) or not _lessons(consumed_lessons):
        raise ValueError("invalid lesson count")
    if consumed_lessons > purchased_lessons:
        raise ValueError("consumed lessons exceed purchased lessons")
    if type(trusted_provider_event_verified) is not bool or type(booking_owner_verified) is not bool:
        raise ValueError("untrusted verification flag type")
    if type(payment_events) is not list or len(payment_events) > _MAX_EVENTS:
        raise ValueError("invalid payment event list")

    seen_ids = set()
    seen_sequences = set()
    events = []
    reasons = []
    for event in payment_events:
        if type(event) is not dict or set(event) != {"id", "booking_id", "sequence", "kind"}:
            raise ValueError("invalid event schema")
        if not _id(event["id"]) or not _id(event["booking_id"]):
            raise ValueError("invalid event identity")
        if type(event["sequence"]) is not int or not 1 <= event["sequence"] <= _MAX_EVENTS:
            raise ValueError("invalid event sequence")
        if type(event["kind"]) is not str or event["kind"] not in _KINDS:
            raise ValueError("invalid event kind")
        if event["booking_id"] != booking_id:
            reasons.append("FOREIGN_BOOKING_EVENT")
        if event["id"] in seen_ids:
            reasons.append("DUPLICATE_EVENT_ID")
        if event["sequence"] in seen_sequences:
            reasons.append("DUPLICATE_EVENT_SEQUENCE")
        seen_ids.add(event["id"])
        seen_sequences.add(event["sequence"])
        events.append(event)

    if sorted(seen_sequences) != list(range(1, len(events) + 1)):
        reasons.append("EVENT_SEQUENCE_GAP")
    if not trusted_provider_event_verified:
        reasons.append("TRUSTED_PROVIDER_EVIDENCE_MISSING")
    if not booking_owner_verified:
        reasons.append("AUTHENTICATED_BOOKING_OWNER_MISSING")

    state = "PENDING"
    # Invalid event sets must not be partially interpreted as trustworthy.
    if not any(r in reasons for r in ("FOREIGN_BOOKING_EVENT", "DUPLICATE_EVENT_ID",
                                      "DUPLICATE_EVENT_SEQUENCE", "EVENT_SEQUENCE_GAP")):
        for event in sorted(events, key=lambda e: e["sequence"]):
            kind = event["kind"]
            if state == "PENDING":
                state = {"succeeded": "PAID", "failed": "FAILED",
                         "cancelled": "CANCELLED", "timed_out": "TIMED_OUT"}[kind]
            elif state == "PAID" and kind == "cancelled":
                state = "CANCELLATION_REVIEW"
                reasons.append("PAID_BOOKING_CANCELLATION_REQUIRES_REVIEW")
            else:
                state = "REVIEW_REQUIRED"
                reasons.append("CONTRADICTORY_PAYMENT_EVENT")
    else:
        state = "REVIEW_REQUIRED"

    if consumed_lessons and state not in ("PAID", "CANCELLATION_REVIEW"):
        reasons.append("CONSUMED_LESSONS_WITHOUT_VERIFIED_PAYMENT")
    if purchased_lessons == 0 and state == "PAID":
        reasons.append("PAID_WITH_ZERO_PURCHASED_LESSONS")

    reasons = sorted(set(reasons))
    safe_preview = state == "PAID" and not reasons
    return {
        "booking_id": booking_id,
        "payment_state_preview": state,
        "preview_status": "REVIEW_ONLY" if safe_preview else "HOLD",
        "purchased_lessons": purchased_lessons,
        "consumed_lessons": consumed_lessons,
        "remaining_lessons_preview": purchased_lessons - consumed_lessons if safe_preview else 0,
        "reasons": reasons,
        "would_be_schedulable_if_integrated": safe_preview and consumed_lessons < purchased_lessons,
        "can_schedule": False,
        "can_charge": False,
        "can_refund": False,
        "can_payout": False,
        "operating_db_connected": False,
        "provider_connected": False,
    }
