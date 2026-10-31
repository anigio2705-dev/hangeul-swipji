"""#106 hypothetical discount/points/cash-equivalent comparison only.

No live price calculation, point credit, payout, database, or policy approval.
Candidate windows/caps are arbitrary test assumptions, not business rules.
"""

POLICIES = frozenset({
    "discount_only", "discount_plus_points", "all_candidates",
})
MAX_AMOUNT = 10**9


def _amount(value, name):
    if type(value) is not int or not 0 <= value <= MAX_AMOUNT:
        raise ValueError(name + " must be a bounded nonnegative integer")
    return value


def simulate_incentive_options(
        *, policy, gross_krw, discount_request_krw, points_request_krw,
        cash_request_krw, age_days, cap_krw):
    """Return only bounded hypothetical incentive candidates.

    Priority for comparison: discount, then points, then cash equivalent.
    Candidate discount expires after day 30; other candidates after day 90.
    No candidate is a real credit or transfer authorization.
    """
    if type(policy) is not str or policy not in POLICIES:
        raise ValueError("unknown hypothetical stacking policy")
    gross_krw = _amount(gross_krw, "gross_krw")
    discount_request_krw = _amount(discount_request_krw, "discount_request_krw")
    points_request_krw = _amount(points_request_krw, "points_request_krw")
    cash_request_krw = _amount(cash_request_krw, "cash_request_krw")
    age_days = _amount(age_days, "age_days")
    cap_krw = _amount(cap_krw, "cap_krw")

    budget = min(gross_krw, cap_krw)
    remaining = budget
    discount = min(discount_request_krw, remaining) if age_days <= 30 else 0
    remaining -= discount
    points = 0
    if policy in {"discount_plus_points", "all_candidates"} and age_days <= 90:
        points = min(points_request_krw, remaining)
        remaining -= points
    cash_candidate = 0
    if policy == "all_candidates" and age_days <= 90:
        cash_candidate = min(cash_request_krw, remaining)
        remaining -= cash_candidate

    return {
        "policy": policy,
        "discount_candidate_krw": discount,
        "points_candidate_krw": points,
        "cash_equivalent_candidate_krw": cash_candidate,
        "hypothetical_payable_after_discount_krw": gross_krw - discount,
        "combined_candidate_krw": discount + points + cash_candidate,
        "hypothetical_cap_krw": budget,
        "unused_hypothetical_cap_krw": remaining,
        "discount_expired": age_days > 30,
        "points_and_cash_expired": age_days > 90,
        "real_money": False,
        "payment_enabled": False,
        "points_credited": False,
        "cash_payout_enabled": False,
        "policy_approved": False,
    }
