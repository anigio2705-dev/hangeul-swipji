"""#113 non-binding monthly lesson refund calculation candidates.

No live billing, refund authorization, statutory cancellation policy or DB writes.
Only use verified completed/unfulfilled counts supplied by a trusted server adapter.
"""
POLICIES = frozenset({"net_paid_prorata", "gross_unused_less_discount"})
MAX_KRW = 1_000_000_000


def _money(value, name):
    if type(value) is not int or not 0 <= value <= MAX_KRW:
        raise ValueError("invalid " + name)
    return value


def _count(value, name):
    if type(value) is not int or not 0 <= value <= 366:
        raise ValueError("invalid " + name)
    return value


def _round_half_up(numerator, denominator):
    """Nonnegative integer arithmetic; deterministic won rounding."""
    return (2 * numerator + denominator) // (2 * denominator)


def simulate_monthly_refund(*, list_price_krw, discount_used_krw,
                            total_lessons, completed_lessons,
                            unfulfilled_lessons, policy):
    """Compare two hypothetical amounts; never approve or execute a refund.

    Unfulfilled means verified non-delivery; future sessions are the remaining
    sessions not yet delivered. Both are only illustrative refundable candidates.
    """
    price = _money(list_price_krw, "list price")
    discount = _money(discount_used_krw, "used discount")
    if discount > price:
        raise ValueError("discount exceeds price")
    total = _count(total_lessons, "total lessons")
    completed = _count(completed_lessons, "completed lessons")
    unfulfilled = _count(unfulfilled_lessons, "unfulfilled lessons")
    if total < 1 or completed + unfulfilled > total:
        raise ValueError("inconsistent monthly lesson counts")
    if type(policy) is not str or policy not in POLICIES:
        raise ValueError("invalid hypothetical refund policy")

    paid = price - discount
    future = total - completed - unfulfilled
    candidate_unused = unfulfilled + future
    if policy == "net_paid_prorata":
        amount = _round_half_up(paid * candidate_unused, total)
    else:
        gross_unused = _round_half_up(price * candidate_unused, total)
        amount = max(0, gross_unused - discount)
    amount = min(paid, amount)
    return {
        "policy": policy,
        "list_price_krw": price,
        "discount_used_krw": discount,
        "net_paid_krw": paid,
        "total_lessons": total,
        "completed_lessons": completed,
        "unfulfilled_lessons": unfulfilled,
        "future_lessons": future,
        "candidate_unused_lessons": candidate_unused,
        "candidate_refund_krw": amount,
        "candidate_retained_krw": paid - amount,
        "rounding": "HALF_UP_WON",
        "legal_policy_approved": False,
        "refund_authorized": False,
        "payment_enabled": False,
        "real_money": False,
        "booking_mutated": False,
        "ledger_mutated": False,
    }
