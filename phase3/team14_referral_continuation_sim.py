"""#105 isolated referral continuation policy candidates; no real reward rights.

No database, payments, live session APIs, or automatic policy activation.
All time windows and count caps below are hypothetical comparison parameters.
"""

POLICY_FIRST_ONLY = "first_only"
POLICY_SAME_TUTOR_30D = "same_tutor_30d"
POLICY_PLATFORM_90D = "platform_90d"
POLICIES = frozenset({
    POLICY_FIRST_ONLY, POLICY_SAME_TUTOR_30D, POLICY_PLATFORM_90D,
})
LESSON_KINDS = frozenset({
    "first", "repeat", "other_tutor", "monthly_renewal",
})


def _flag(value, name):
    if type(value) is not bool:
        raise ValueError(name + " must be bool")
    return value


def _count(value, name):
    if type(value) is not int or value < 0 or value > 1000000:
        raise ValueError(name + " must be a bounded nonnegative integer")
    return value


def simulate_referral_continuation(
        *, policy, lesson_kind, same_tutor, days_since_first,
        previous_rewarded_count, payment_confirmed, lesson_completed,
        refunded, referrer_eligible):
    """Compare hypothetical referral continuation, not payout authorization.

    A: first lesson only, once.
    B: first/repeat/monthly with original tutor within 30 days, up to 3.
    C: any tutor and monthly renewal within 90 days, up to 10.
    Neither time window nor cap is an approved business rule.
    """
    if type(policy) is not str or policy not in POLICIES:
        raise ValueError("unknown hypothetical continuation policy")
    if type(lesson_kind) is not str or lesson_kind not in LESSON_KINDS:
        raise ValueError("unknown lesson kind")
    same_tutor = _flag(same_tutor, "same_tutor")
    payment_confirmed = _flag(payment_confirmed, "payment_confirmed")
    lesson_completed = _flag(lesson_completed, "lesson_completed")
    refunded = _flag(refunded, "refunded")
    referrer_eligible = _flag(referrer_eligible, "referrer_eligible")
    days_since_first = _count(days_since_first, "days_since_first")
    previous_rewarded_count = _count(
        previous_rewarded_count, "previous_rewarded_count")
    if lesson_kind == "other_tutor" and same_tutor:
        raise ValueError("other_tutor must have same_tutor=False")
    if lesson_kind == "first" and previous_rewarded_count:
        raise ValueError("first lesson cannot have earlier rewarded lessons")

    if policy == POLICY_FIRST_ONLY:
        within_scope = lesson_kind == "first"
        within_window = True
        under_cap = previous_rewarded_count < 1
        candidate_limit = 1
        candidate_window_days = None
    elif policy == POLICY_SAME_TUTOR_30D:
        within_scope = same_tutor and lesson_kind != "other_tutor"
        within_window = days_since_first <= 30
        under_cap = previous_rewarded_count < 3
        candidate_limit = 3
        candidate_window_days = 30
    else:
        within_scope = True
        within_window = days_since_first <= 90
        under_cap = previous_rewarded_count < 10
        candidate_limit = 10
        candidate_window_days = 90

    if refunded:
        reason = "REFUND_VOID"
    elif not referrer_eligible:
        reason = "REFERRER_INELIGIBLE"
    elif not payment_confirmed:
        reason = "WAIT_PAYMENT"
    elif not lesson_completed:
        reason = "WAIT_COMPLETION"
    elif not within_scope:
        reason = "OUT_OF_SCOPE"
    elif not within_window:
        reason = "WINDOW_EXPIRED"
    elif not under_cap:
        reason = "COUNT_CAP_REACHED"
    else:
        reason = "SIMULATED_CANDIDATE"

    return {
        "policy": policy,
        "lesson_kind": lesson_kind,
        "reason": reason,
        "candidate_eligible": reason == "SIMULATED_CANDIDATE",
        "candidate_window_days": candidate_window_days,
        "candidate_count_cap": candidate_limit,
        "real_money": False,
        "payment_enabled": False,
        "policy_approved": False,
        "payout_authorized": False,
    }
