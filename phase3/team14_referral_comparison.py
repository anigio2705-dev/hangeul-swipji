"""#102: nonbinding comparison of direct/multilevel referral options.

A deterministic, read-only product component. This does NOT establish legal,
tax, reward, retention or payout policy. No I/O, identity proof or money movement.
"""
from datetime import datetime, timedelta, timezone
import re

_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_UTC = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z\Z")
_EVENTS = frozenset(("BOOKING_PAID", "LESSON_COMPLETED", "MONTH_RENEWED"))
_CANDIDATE_KEYS = frozenset(("candidate_id", "max_depth", "duration_days", "eligible_events"))
_CONTEXT_KEYS = frozenset(("referral_chain", "referred_at_utc", "transaction_at_utc",
                           "as_of_utc", "event", "refund_pending",
                           "fixture_payment_evidence_present"))


def _id(value):
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise ValueError("invalid identifier")
    return value


def _utc(value):
    if type(value) is not str or _UTC.fullmatch(value) is None:
        raise ValueError("explicit UTC timestamp required")
    try:
        result = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("invalid UTC timestamp") from exc
    if result.tzinfo != timezone.utc:
        raise ValueError("UTC only")
    return result


def _integer(value, low, high, field):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("invalid " + field)
    return value


def compare_referral_options(candidates, context):
    """Compare candidate depth, duration, and eligible transaction kinds.

    Chain is [referred_user, direct_referrer, next_ancestor, ...]. All links
    and payment evidence are UNTRUSTED fixture claims. Returned depth matches
    are hypothetical only; no referral or payout is authorized.
    """
    if type(candidates) not in (list, tuple) or not 1 <= len(candidates) <= 16:
        raise ValueError("invalid candidates")
    if type(context) is not dict or frozenset(context) != _CONTEXT_KEYS:
        raise ValueError("invalid scenario schema")
    chain = context["referral_chain"]
    if type(chain) not in (list, tuple) or not 2 <= len(chain) <= 11:
        raise ValueError("invalid referral chain")
    members = tuple(_id(x) for x in chain)
    if len(set(members)) != len(members):
        raise ValueError("duplicate or cyclic referral chain")
    referred = _utc(context["referred_at_utc"])
    transaction = _utc(context["transaction_at_utc"])
    now = _utc(context["as_of_utc"])
    if not referred <= transaction <= now:
        raise ValueError("invalid event chronology")
    event = context["event"]
    if type(event) is not str or event not in _EVENTS:
        raise ValueError("invalid transaction event")
    for field in ("refund_pending", "fixture_payment_evidence_present"):
        if type(context[field]) is not bool:
            raise ValueError("invalid " + field)

    comparisons = []
    seen = set()
    for candidate in candidates:
        if type(candidate) is not dict or frozenset(candidate) != _CANDIDATE_KEYS:
            raise ValueError("invalid candidate schema")
        cid = _id(candidate["candidate_id"])
        if cid in seen:
            raise ValueError("duplicate candidate id")
        seen.add(cid)
        depth = _integer(candidate["max_depth"], 1, 10, "max_depth")
        duration = _integer(candidate["duration_days"], 0, 3650, "duration_days")
        events = candidate["eligible_events"]
        if type(events) not in (list, tuple) or not 1 <= len(events) <= 3:
            raise ValueError("invalid eligible events")
        if any(type(e) is not str or e not in _EVENTS for e in events):
            raise ValueError("unknown eligible event")
        if len(set(events)) != len(events):
            raise ValueError("duplicate eligible event")
        reasons = []
        if event not in events:
            reasons.append("EVENT_NOT_IN_CANDIDATE")
        if transaction > referred + timedelta(days=duration):
            reasons.append("CANDIDATE_PERIOD_EXPIRED")
        if context["refund_pending"]:
            reasons.append("REFUND_PENDING")
        if not context["fixture_payment_evidence_present"]:
            reasons.append("NO_FIXTURE_PAYMENT_EVIDENCE")
        matched = min(depth, len(members) - 1) if not reasons else 0
        comparisons.append({
            "candidate_id": cid,
            "model": "DIRECT_ONLY" if depth == 1 else "MULTILEVEL",
            "max_depth": depth,
            "duration_days": duration,
            "eligible_events": sorted(events),
            "hypothetical_depths": list(range(1, matched + 1)),
            "hypothetical_referrer_count": matched,
            "review_reasons": sorted(reasons),
            "review_status": "COMPARE_ONLY" if not reasons else "BLOCKED_FIXTURE",
            "identity_verified": False,
            "transaction_verified": False,
            "policy_approved": False,
            "legal_tax_approved": False,
            "can_create_reward": False,
            "can_payout": False,
            "can_modify_operating_db": False,
        })
    return {
        "comparison_count": len(comparisons),
        "chain_length": len(members),
        "transaction_event": event,
        "results": comparisons,
        "policy_approved": False,
        "can_activate_real_money": False,
    }
