"""#104 isolated, hypothetical reward timing comparison; NEVER settles or pays.

This pure simulation deliberately does not import the live reservation/payment API.
Policy selection, refund windows, eligibility and settlement remain unapproved.
"""

POLICIES = frozenset({"on_payment", "on_completion", "after_refund_window"})
MAX_WINDOW_SECONDS = 90 * 24 * 60 * 60


def _timestamp(value, name, *, optional=False):
    if optional and value is None:
        return None
    if type(value) is not int or value < 0:
        raise ValueError(name + " must be a nonnegative integer Unix timestamp")
    return value


def simulate_reward_timing(*, payment_at, completion_at, refund_at=None,
                           as_of, policy, refund_window_seconds=7 * 86400):
    """Return a hypothetical timing state, NOT an authorization to transfer funds.

    A: on_payment - earliest candidate; refund risk persists.
    B: on_completion - lesson must be finished and payment captured.
    C: after_refund_window - wait until both are done plus a test window.

    The safe_to_confirm flag is a *simulation predicate*, not an approved policy.
    """
    payment_at = _timestamp(payment_at, "payment_at", optional=True)
    completion_at = _timestamp(completion_at, "completion_at", optional=True)
    refund_at = _timestamp(refund_at, "refund_at", optional=True)
    as_of = _timestamp(as_of, "as_of")
    if type(policy) is not str or policy not in POLICIES:
        raise ValueError("unknown hypothetical policy")
    if type(refund_window_seconds) is not int or not 0 <= refund_window_seconds <= MAX_WINDOW_SECONDS:
        raise ValueError("invalid hypothetical refund window")
    if refund_at is not None and (payment_at is None or refund_at < payment_at):
        raise ValueError("refund must follow a captured payment")

    refunded = refund_at is not None and refund_at <= as_of
    paid = payment_at is not None and payment_at <= as_of
    completed = completion_at is not None and completion_at <= as_of
    safe_at = (max(payment_at, completion_at) + refund_window_seconds
               if payment_at is not None and completion_at is not None else None)
    if policy == "on_payment":
        trigger_at = payment_at
    elif policy == "on_completion":
        trigger_at = max(payment_at, completion_at) if paid and completed else None
    else:
        trigger_at = safe_at if paid and completed else None

    triggered = bool(not refunded and trigger_at is not None and trigger_at <= as_of)
    safe_to_confirm = bool(triggered and refund_at is None and paid and completed and
                           safe_at is not None and as_of >= safe_at)
    if refunded:
        state = "VOID_REFUND"
    elif not paid:
        state = "WAIT_PAYMENT"
    elif not triggered and not completed and policy != "on_payment":
        state = "WAIT_LESSON"
    elif not triggered:
        state = "WAIT_TRIGGER"
    elif not safe_to_confirm:
        state = "PROVISIONAL_REFUND_RISK"
    else:
        state = "SIMULATED_WINDOW_CLOSED"
    return {
        "policy": policy, "state": state, "candidate_trigger_at": trigger_at,
        "candidate_triggered": triggered, "safe_to_confirm_simulated": safe_to_confirm,
        "refund_window_seconds": refund_window_seconds,
        "real_money": False, "policy_approved": False, "payment_enabled": False,
    }
