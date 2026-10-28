"""Team11 v1 shared boundary for team13 matching and team14 simulated settlement.

Pure functions. No persistence, payment, network, or runtime integration.
"""
from dataclasses import dataclass

from common_compat_adapter import (
    from_legacy_user, from_candidate, matching_side, normalize_error,
    normalize_match_state, month_lesson_reference,
)
from common_contract import validate_id, validate_state, validate_amount_minor

CONTRACT_VERSION = "team11.v1"
LESSON_KINDS = frozenset(("conversation_partner", "professional_teacher"))
EVENT_TYPES = frozenset(("lesson.completed", "lesson.refunded"))


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    error_code: str | None


def authorize_provider(user, kind, *, candidate=False, approvals=None):
    """Fail closed; legacy teacher may serve conversation as existing service permits."""
    if kind not in LESSON_KINDS:
        return AccessDecision(False, "VALIDATION_ERROR")
    view = (from_candidate(user, approvals if approvals is not None else {})
            if candidate else from_legacy_user(user))
    return AccessDecision(view.may_provide(kind), None if view.may_provide(kind) else "FORBIDDEN")


def authorize_student(user, *, candidate=False, approvals=None):
    view = (from_candidate(user, approvals if approvals is not None else {})
            if candidate else from_legacy_user(user))
    allowed = matching_side(view, "learner")
    return AccessDecision(allowed, None if allowed else "FORBIDDEN")


def lesson_completion_event(*, event_id, booking_id, learner_id, provider_id,
                            kind, amount_krw, state="completed"):
    """Explicit event ID enables downstream idempotency; no implicit ledger write."""
    ids = (event_id, booking_id, learner_id, provider_id)
    for value in ids:
        validate_id(value)
    if learner_id == provider_id:
        raise ValueError("self lesson prohibited")
    if kind not in LESSON_KINDS or state != "completed":
        raise ValueError("completion requires valid lesson kind and completed state")
    validate_state(state, "booking")
    validate_amount_minor(amount_krw)
    return {
        "contract_version": CONTRACT_VERSION,
        "event_type": "lesson.completed",
        "event_id": event_id,
        "booking_id": booking_id,
        "learner_id": learner_id,
        "provider_id": provider_id,
        "lesson_kind": kind,
        "booking_state": state,
        "amount": amount_krw,
        "currency": "KRW",
    }


def validate_completion_event(event):
    """Reject partial, extra or forged event fields; never accept bool as amount."""
    if not isinstance(event, dict):
        raise ValueError("event must be a mapping")
    expected = lesson_completion_event(
        event_id=event["event_id"], booking_id=event["booking_id"],
        learner_id=event["learner_id"], provider_id=event["provider_id"],
        kind=event["lesson_kind"], amount_krw=event["amount"],
        state=event["booking_state"],
    )
    if event != expected:
        raise ValueError("event contract mismatch")
    return expected


def settlement_reference(event, *, month_id, lesson_index):
    """Team14 simulator adapter: scoped index only, never asserts ledger payment."""
    verified = validate_completion_event(event)
    reference = month_lesson_reference(month_id, lesson_index, verified["currency"])
    return {**reference, "booking_id": verified["booking_id"],
            "event_id": verified["event_id"], "amount_krw": verified["amount"]}


def http_error_contract(status):
    return {"code": normalize_error(status), "http_status": status}


def match_state_contract(state):
    return normalize_match_state(state)
