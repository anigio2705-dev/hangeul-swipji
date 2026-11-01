"""#127: deterministic candidate-only payout-rule review, never policy approval.

All amounts are integer *minor units*; FX is an untrusted rational quote of
target-minor/source-minor. No real FX, tax, legal, banking, provider or payout I/O.
"""
from datetime import datetime, timedelta, timezone
import re

_CYCLES = frozenset(("WEEKLY", "BIWEEKLY", "MONTHLY"))
_FIELDS = frozenset((
    "candidate_id", "cycle", "minimum_target_minor", "fee_bps",
    "fx_numerator", "fx_denominator", "hold_days", "max_retries",
    "retry_delay_hours",
))
_CONTEXT = frozenset((
    "gross_source_minor", "settled_at_utc", "as_of_utc", "failed_attempts",
    "last_failed_at_utc", "disputed", "refund_pending",
))
_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


def _int(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("invalid " + label)
    return value


def _utc(value):
    if type(value) is not str or len(value) > 40 or not value.endswith("Z"):
        raise ValueError("explicit UTC timestamp required")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("invalid UTC timestamp") from exc
    if parsed.utcoffset() != timedelta(0):
        raise ValueError("UTC only")
    return parsed


def _stamp(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="auto").replace("+00:00", "Z")


def _next_cycle(now, cycle):
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if cycle == "WEEKLY":
        days = (7 - now.weekday()) % 7
        result = midnight + timedelta(days=days)
        return result if result > now else result + timedelta(days=7)
    if cycle == "BIWEEKLY":
        anchor = datetime(2026, 1, 5, tzinfo=timezone.utc)
        elapsed = (now - anchor).total_seconds()
        periods = max(0, int(elapsed // (14 * 86400)) + 1)
        return anchor + timedelta(days=14 * periods)
    year, month = now.year, now.month
    if month == 12:
        return midnight.replace(year=year + 1, month=1, day=1)
    return midnight.replace(month=month + 1, day=1)


def review_payout_candidate(candidate, context):
    """Return a bounded, nonbinding comparison. Never authorize a transfer."""
    if type(candidate) is not dict or frozenset(candidate) != _FIELDS:
        raise ValueError("invalid candidate schema")
    if type(context) is not dict or frozenset(context) != _CONTEXT:
        raise ValueError("invalid context schema")
    ident = candidate["candidate_id"]
    if type(ident) is not str or _ID.fullmatch(ident) is None:
        raise ValueError("invalid candidate_id")
    cycle = candidate["cycle"]
    if type(cycle) is not str or cycle not in _CYCLES:
        raise ValueError("invalid cycle")
    minimum = _int(candidate["minimum_target_minor"], 0, 10**12, "minimum")
    bps = _int(candidate["fee_bps"], 0, 10000, "fee_bps")
    numerator = _int(candidate["fx_numerator"], 1, 10**9, "fx_numerator")
    denominator = _int(candidate["fx_denominator"], 1, 10**9, "fx_denominator")
    hold_days = _int(candidate["hold_days"], 0, 365, "hold_days")
    retries = _int(candidate["max_retries"], 0, 20, "max_retries")
    retry_hours = _int(candidate["retry_delay_hours"], 1, 720, "retry_delay_hours")
    gross = _int(context["gross_source_minor"], 0, 10**12, "gross")
    attempts = _int(context["failed_attempts"], 0, 100, "failed_attempts")
    for field in ("disputed", "refund_pending"):
        if type(context[field]) is not bool:
            raise ValueError("invalid " + field)
    settled, now = _utc(context["settled_at_utc"]), _utc(context["as_of_utc"])
    if settled > now:
        raise ValueError("future settlement is not trusted")
    last_raw = context["last_failed_at_utc"]
    if attempts == 0 and last_raw is not None:
        raise ValueError("failure timestamp without attempt")
    if attempts and last_raw is None:
        raise ValueError("missing failure timestamp")
    last = _utc(last_raw) if last_raw is not None else None
    if last is not None and (last < settled or last > now):
        raise ValueError("invalid failure chronology")
    # Deterministic half-up arithmetic without floating point or FX execution.
    fee = (gross * bps + 5000) // 10000
    net = gross - fee
    target = (net * numerator * 2 + denominator) // (2 * denominator)
    # The above integer expression rounds ties upward for integer minor units.
    reasons = []
    if target < minimum:
        reasons.append("BELOW_MINIMUM")
    hold_until = settled + timedelta(days=hold_days)
    if now < hold_until:
        reasons.append("HOLD_PERIOD_ACTIVE")
    if context["disputed"]:
        reasons.append("DISPUTE_OPEN")
    if context["refund_pending"]:
        reasons.append("REFUND_PENDING")
    if attempts >= retries and attempts > 0:
        reasons.append("RETRY_LIMIT_REACHED")
    if last is not None and now < last + timedelta(hours=retry_hours):
        reasons.append("RETRY_COOLDOWN_ACTIVE")
    next_cycle = _next_cycle(now, cycle)
    return {
        "candidate_id": ident,
        "cycle": cycle,
        "next_cycle_review_at_utc": _stamp(next_cycle),
        "hold_until_utc": _stamp(hold_until),
        "source_gross_minor": gross,
        "hypothetical_fee_minor": fee,
        "hypothetical_net_source_minor": net,
        "hypothetical_target_minor": target,
        "minimum_target_minor": minimum,
        "failed_attempts": attempts,
        "review_status": "HOLD" if reasons else "REVIEW_ONLY",
        "review_reasons": sorted(reasons),
        "policy_approved": False,
        "fx_quote_verified": False,
        "recipient_verified": False,
        "can_payout": False,
        "can_retry_payment": False,
        "can_modify_operating_db": False,
        "can_activate_real_money": False,
    }
