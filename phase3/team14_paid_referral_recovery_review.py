"""#116: already-paid referral recovery alternatives, REVIEW ONLY.

This module uses #114/#115/#120 isolated integer-KRW simulation results.
All balances, future settlements and recovery caps are UNVERIFIED TEST INPUTS.
No debit, offset, claim, payout, operating database, or policy activation occurs.
"""
from team14_financial_edge_matrix import calculate_edge_case
from team14_transaction_subledger import _amount


def review_paid_referral_recovery(*, gross_krw, allocations, referral_weights,
                                  refunds, already_paid_referral_krw,
                                  available_balance_fixture_krw,
                                  future_settlement_fixture_krw,
                                  recovery_cap_fixture_krw=None):
    """Compare three nonbinding paths; never turn fixtures into authority.

    If the legal/contractual recovery cap is unknown, no recoverable amount
    is approved. Suggested amounts are strictly hypothetical ceilings.
    """
    balance = _amount(available_balance_fixture_krw, "balance fixture")
    future = _amount(future_settlement_fixture_krw, "future fixture")
    if recovery_cap_fixture_krw is not None:
        cap = _amount(recovery_cap_fixture_krw, "recovery cap fixture")
    else:
        cap = None
    calc = calculate_edge_case(
        gross_krw=gross_krw, allocations=allocations,
        referral_weights=referral_weights, refunds=refunds,
        already_paid_referral_krw=already_paid_referral_krw)
    exposure = calc["potential_paid_exposure_krw"]
    # Unknown legal/contractual cap means ZERO approved recovery.
    # The illustrative comparison may still show possible coverage.
    illustrative_cap = min(exposure, cap) if cap is not None else exposure
    balance_option = min(illustrative_cap, balance)
    future_option = min(illustrative_cap - balance_option, future)
    manual_option = illustrative_cap - balance_option - future_option
    if min(balance_option, future_option, manual_option) < 0:
        raise AssertionError("negative proposed recovery")
    if sum((balance_option, future_option, manual_option)) != illustrative_cap:
        raise AssertionError("nonconserving recovery alternatives")
    return {
        "already_paid_referral_krw": calc["already_paid_referral_krw"],
        "reversed_referral_krw": calc["total_bucket_reversed_krw"]["referral"],
        "potential_exposure_krw": exposure,
        "recovery_cap_fixture_krw": cap,
        "recovery_cap_verified": False,
        "illustrative_recovery_ceiling_krw": illustrative_cap,
        "not_in_illustrative_scope_krw": exposure - illustrative_cap,
        "alternatives": [
            {"kind": "existing_balance_review", "illustrative_krw": balance_option,
             "actual_offset_krw": 0, "requires_verified_balance": True},
            {"kind": "future_settlement_review", "illustrative_krw": future_option,
             "actual_offset_krw": 0, "requires_verified_future_settlement": True},
            {"kind": "manual_recovery_limit_review", "illustrative_krw": manual_option,
             "actual_recovered_krw": 0, "requires_legal_policy_approval": True},
        ],
        "uncovered_illustrative_krw": manual_option,
        "recommended_state": "NO_ACTION" if exposure == 0 else "MANUAL_REVIEW_REQUIRED",
        "approved_recovery_krw": 0,
        "actual_balance_debited_krw": 0,
        "actual_future_settlement_offset_krw": 0,
        "actual_recovered_krw": 0,
        "automatic_clawback": False,
        "policy_approved": False,
        "legal_recovery_approved": False,
        "real_money": False,
        "payout_authorized": False,
        "operating_db_connected": False,
        "simulation_only": True,
    }
