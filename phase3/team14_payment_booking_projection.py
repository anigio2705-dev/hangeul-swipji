"""Original 160 task #123: isolated booking/remaining-lesson payment-state reconciliation.

Pure, deterministic state projection. Event authenticity, external provider
status and persistent booking updates are NOT established by this module.
Never invokes payment APIs, charges, refunds or production storage.
"""
import re

_MAX_EVENTS = 1000
_MAX_LESSONS = 1000
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
_BOOKING_FIELDS = frozenset({"booking_id", "payment_id", "lesson_count", "completed_lessons"})
_EVENT_FIELDS = frozenset({"event_id", "payment_id", "sequence", "outcome"})
_OUTCOMES = frozenset({"SUCCESS", "FAILURE", "TIMEOUT", "CANCELED"})


def _id(value, name):
    if type(value) is not str or not _ID.fullmatch(value):
        raise ValueError("invalid " + name)
    return value


def _integer(value, name, *, minimum=0, maximum=_MAX_LESSONS):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("invalid " + name)
    return value


def reconcile_payment_booking(*, booking, events):
    """Project trusted-*candidate* payment events into a review-only booking state.

    A stable gateway sequence orders events, not arrival order. Replayed identical
    event IDs are idempotent; conflicting IDs or sequences are rejected. Invalid
    payment-state transitions fail closed to REVIEW_REQUIRED, never PAID.
    The caller MUST authenticate gateway signatures and persist state atomically
    before this projection can be integrated into an actual booking system.
    """
    if type(booking) is not dict or set(booking) != _BOOKING_FIELDS:
        raise ValueError("invalid booking fields")
    booking_id = _id(booking["booking_id"], "booking_id")
    payment_id = _id(booking["payment_id"], "payment_id")
    count = _integer(booking["lesson_count"], "lesson_count", minimum=1)
    completed = _integer(booking["completed_lessons"], "completed_lessons")
    if completed > count:
        raise ValueError("completed lessons exceed purchased lessons")
    if type(events) not in (tuple, list) or len(events) > _MAX_EVENTS:
        raise ValueError("invalid events")

    by_id, by_sequence = {}, {}
    for event in events:
        if type(event) is not dict or set(event) != _EVENT_FIELDS:
            raise ValueError("invalid event fields")
        event_id = _id(event["event_id"], "event_id")
        if _id(event["payment_id"], "event.payment_id") != payment_id:
            raise ValueError("payment_id mismatch")
        sequence = _integer(event["sequence"], "sequence", minimum=1, maximum=1000000000)
        outcome = event["outcome"]
        if type(outcome) is not str or outcome not in _OUTCOMES:
            raise ValueError("invalid outcome")
        fingerprint = (sequence, outcome)
        if event_id in by_id:
            if by_id[event_id] != fingerprint:
                raise ValueError("conflicting replayed event_id")
            continue
        if sequence in by_sequence:
            raise ValueError("conflicting event sequence")
        by_id[event_id] = fingerprint
        by_sequence[sequence] = outcome

    state = "PENDING"
    history = []
    for sequence, outcome in sorted(by_sequence.items()):
        history.append({"sequence": sequence, "outcome": outcome})
        if state == "PENDING":
            state = {"SUCCESS": "PAID", "FAILURE": "FAILED",
                     "TIMEOUT": "TIMED_OUT", "CANCELED": "CANCELED"}[outcome]
        elif state == "PAID" and outcome == "CANCELED":
            state = "CANCELED"
        else:
            # Later success after failure/timeout/cancellation, repeated success,
            # or contradictory terminal notifications require provider review.
            state = "DISPUTED"

    manual_review = state == "DISPUTED" or (completed > 0 and state != "PAID")
    if manual_review:
        booking_status = "REVIEW_REQUIRED"
    elif state == "PENDING":
        booking_status = "AWAITING_PAYMENT"
    elif state == "PAID":
        booking_status = "COMPLETED" if completed == count else "ACTIVE"
    else:
        booking_status = {"FAILED": "PAYMENT_FAILED", "TIMED_OUT": "PAYMENT_TIMED_OUT",
                          "CANCELED": "CANCELED"}[state]
    remaining = count - completed if state == "PAID" else 0
    return {
        "task": 123,
        "status": "ISOLATED_REVIEW_ONLY",
        "booking_id": booking_id,
        "payment_id": payment_id,
        "payment_state": state,
        "booking_state": booking_status,
        "purchased_lessons": count,
        "completed_lessons": completed,
        "remaining_bookable_lessons": remaining,
        "manual_review_required": manual_review,
        "unique_event_count": len(by_id),
        "ordered_event_history": history,
        "payment_event_provenance_verified": False,
        "operating_db_connected": False,
        "real_money_enabled": False,
        "provider_api_called": False,
        "production_booking_updated": False,
    }
