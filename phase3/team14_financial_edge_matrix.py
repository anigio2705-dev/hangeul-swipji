"""#120 isolated integer-KRW financial edge-case calculator.

Executable examples only. Referral weights are test fixtures, not an approved
multi-level compensation policy. No booking, operating DB, payment, payout or
automatic clawback integration. Never treat a simulated amount as payable.
"""
from team14_reversal_subledger import SimulatedReversalLedger
from team14_transaction_subledger import BUCKETS, MAX_KRW, _amount


def _split_krw(total, weights):
    """Stable largest-remainder allocation; never over-allocate a bucket."""
    _amount(total, "total")
    if type(weights) not in (list, tuple) or not 1 <= len(weights) <= 8:
        raise ValueError("expected one to eight referral levels")
    if any(type(w) is not int or w < 0 or w > MAX_KRW for w in weights):
        raise ValueError("invalid weights")
    denominator = sum(weights)
    if denominator == 0:
        if total:
            raise ValueError("nonzero amount without positive weights")
        return tuple(0 for _ in weights)
    if total > denominator and any(w == 0 for w in weights):
        # A zero-weight level always remains zero; other levels may exceed
        # their input weights for normal weighted allocation.
        pass
    base, fractions = [], []
    for index, weight in enumerate(weights):
        whole, rem = divmod(total * weight, denominator)
        base.append(whole)
        fractions.append((-rem, index))
    for _, index in sorted(fractions)[:total - sum(base)]:
        base[index] += 1
    if sum(base) != total or min(base) < 0:
        raise AssertionError("KRW allocation conservation")
    return tuple(base)


def calculate_edge_case(*, gross_krw, allocations, referral_weights,
                        refunds=(), already_paid_referral_krw=0):
    """Run #120 examples against the actual #114/#115 isolated ledgers.

    refunds: sequence of (partial_refund|full_refund|cancel, integer_KRW).
    A paid referral is historical test input, NEVER an instruction to pay or
    recover money. Return an exposure flag for a human decision only.
    """
    if type(allocations) is not dict or set(allocations) != set(BUCKETS):
        raise ValueError("all four allocations required")
    gross = _amount(gross_krw, "gross_krw")
    if gross == 0:
        raise ValueError("gross must be positive")
    amounts = {k: _amount(allocations[k], k) for k in BUCKETS}
    if sum(amounts.values()) != gross:
        raise ValueError("allocations must conserve gross")
    if type(referral_weights) not in (list, tuple) or not 1 <= len(referral_weights) <= 8:
        raise ValueError("one to eight referral weights required")
    if any(type(w) is not int or not 1 <= w <= 10000 for w in referral_weights):
        raise ValueError("referral weights must be positive test integers")
    paid = _amount(already_paid_referral_krw, "already_paid_referral_krw")
    if paid > amounts["referral"]:
        raise ValueError("paid referral exceeds recorded referral allocation")
    if type(refunds) not in (tuple, list) or len(refunds) > 100:
        raise ValueError("invalid refund sequence")
    for event in refunds:
        if type(event) not in (tuple, list) or len(event) != 2:
            raise ValueError("invalid refund event")
        if type(event[0]) is not str or event[0] not in (
                "partial_refund", "full_refund", "cancel"):
            raise ValueError("invalid refund kind")
        _amount(event[1], "refund amount")
        if event[1] == 0:
            raise ValueError("refund must be positive")

    levels = list(_split_krw(amounts["referral"], referral_weights))
    original_levels = tuple(levels)
    ledger = SimulatedReversalLedger()
    try:
        ledger.record(
            tx_id="task120_tx", evidence_id="task120_fixture", gross_krw=gross,
            **{k + "_krw": v for k, v in amounts.items()})
        results = []
        reversed_total = {k: 0 for k in BUCKETS}
        for i, (kind, refund_amount) in enumerate(refunds):
            result = ledger.reverse(
                reversal_id="task120_rev_" + str(i),
                tx_id="task120_tx",
                evidence_id="task120_fixture_" + str(i),
                event_kind=kind, refund_krw=refund_amount)
            entries = {e["bucket"]: e["amount_krw"]
                       for e in result["reversed_entries"]}
            for bucket in BUCKETS:
                reversed_total[bucket] += entries[bucket]
                if reversed_total[bucket] > amounts[bucket]:
                    raise AssertionError("bucket over-reversal")
            referral_reversal = entries["referral"]
            # Allocate against REMAINING level balances to prevent negative
            # deltas after repeated 1-KRW and partial refunds.
            level_deductions = _split_krw(referral_reversal, levels)
            if any(d > b for d, b in zip(level_deductions, levels)):
                raise AssertionError("referral level over-reversal")
            levels = [b - d for b, d in zip(levels, level_deductions)]
            results.append({
                "event_kind": kind, "refund_krw": refund_amount,
                "bucket_reversed_krw": entries,
                "referral_level_reversed_krw": level_deductions,
                "remaining_krw": result["remaining_krw"],
            })
        if sum(reversed_total.values()) + (
                gross - sum(e["refund_krw"] for e in results)) != gross:
            raise AssertionError("total refund conservation")
        if sum(levels) + reversed_total["referral"] != amounts["referral"]:
            raise AssertionError("multi-level referral conservation")
        exposure = min(paid, reversed_total["referral"])
        return {
            "gross_krw": gross,
            "original_referral_level_krw": original_levels,
            "remaining_referral_level_krw": tuple(levels),
            "total_refunded_krw": sum(e["refund_krw"] for e in results),
            "remaining_transaction_krw": gross - sum(
                e["refund_krw"] for e in results),
            "total_bucket_reversed_krw": reversed_total,
            "events": results,
            "already_paid_referral_krw": paid,
            "potential_paid_exposure_krw": exposure,
            "manual_recovery_review_required": exposure > 0,
            "real_money": False,
            "policy_approved": False,
            "payment_enabled": False,
            "refund_executed": False,
            "automatic_clawback": False,
            "payout_authorized": False,
            "operating_db_connected": False,
        }
    finally:
        ledger.close()
