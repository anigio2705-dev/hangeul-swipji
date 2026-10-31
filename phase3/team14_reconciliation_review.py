"""#128: isolated reconciliation of payment, refund, ledger and payout evidence.

Review-only, pure in-memory. This does not contact a provider, access an
operating database, release money or approve a policy. Caller-supplied records
are untrusted unless a future authenticated server adapter verifies them.
"""
import re

_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_ALLOWED_PAYOUT_STATES = frozenset(("paid", "pending", "failed"))


def _id(value):
    return type(value) is str and _ID.fullmatch(value) is not None


def _amount(value):
    return type(value) is int and 0 <= value <= 10**12


def _records(items, booking_id, category, allowed_states):
    if type(items) is not list or len(items) > 1000:
        raise ValueError("invalid " + category + " records")
    accepted, ids, reasons = [], set(), []
    for row in items:
        if type(row) is not dict or set(row) != {
                "id", "booking_id", "amount_krw", "state"}:
            raise ValueError("invalid " + category + " schema")
        if not _id(row["id"]) or not _id(row["booking_id"]):
            raise ValueError("invalid record identity")
        if not _amount(row["amount_krw"]):
            raise ValueError("invalid KRW amount")
        if type(row["state"]) is not str or row["state"] not in allowed_states:
            raise ValueError("invalid record state")
        if row["id"] in ids:
            reasons.append(category + "_DUPLICATE_ID")
        ids.add(row["id"])
        if row["booking_id"] != booking_id:
            reasons.append(category + "_FOREIGN_BOOKING")
        accepted.append(row)
    return accepted, reasons


def reconcile_booking(*, booking_id, payments, refunds, ledger, payouts,
                      trusted_evidence_verified=False, policy_approved=False):
    """Return deterministic fail-closed review, never an active payout command.

    Ledger entries use signed `amount_krw` and one of payment/refund/payout:
    payment +gross, refund -refund, payout -paid. A pending/failed payout is
    not counted as disbursed. Matching amounts are necessary but never
    sufficient to authorize a real payment.
    """
    if not _id(booking_id):
        raise ValueError("invalid booking identity")
    if type(trusted_evidence_verified) is not bool or type(policy_approved) is not bool:
        raise ValueError("verification flags must be boolean")
    p, rp = _records(payments, booking_id, "payment", {"succeeded"})
    r, rr = _records(refunds, booking_id, "refund", {"succeeded"})
    o, ro = _records(payouts, booking_id, "payout", _ALLOWED_PAYOUT_STATES)
    if type(ledger) is not list or len(ledger) > 1000:
        raise ValueError("invalid ledger")
    reasons = rp + rr + ro
    seen = set()
    sums = {"payment": 0, "refund": 0, "payout": 0}
    for row in ledger:
        if type(row) is not dict or set(row) != {
                "id", "booking_id", "kind", "amount_krw"}:
            raise ValueError("invalid ledger schema")
        if not _id(row["id"]) or not _id(row["booking_id"]):
            raise ValueError("invalid ledger identity")
        if type(row["kind"]) is not str or row["kind"] not in sums:
            raise ValueError("invalid ledger kind")
        amount = row["amount_krw"]
        if type(amount) is not int or abs(amount) > 10**12:
            raise ValueError("invalid signed ledger amount")
        if row["id"] in seen:
            reasons.append("ledger_DUPLICATE_ID")
        seen.add(row["id"])
        if row["booking_id"] != booking_id:
            reasons.append("ledger_FOREIGN_BOOKING")
        if (row["kind"] == "payment" and amount < 0) or (
                row["kind"] != "payment" and amount > 0):
            reasons.append("ledger_INVALID_SIGN")
        sums[row["kind"]] += amount

    paid = sum(x["amount_krw"] for x in p)
    refunded = sum(x["amount_krw"] for x in r)
    disbursed = sum(x["amount_krw"] for x in o if x["state"] == "paid")
    if paid != sums["payment"]:
        reasons.append("PAYMENT_LEDGER_MISMATCH")
    if refunded != -sums["refund"]:
        reasons.append("REFUND_LEDGER_MISMATCH")
    if disbursed != -sums["payout"]:
        reasons.append("PAYOUT_LEDGER_MISMATCH")
    if refunded > paid:
        reasons.append("REFUND_EXCEEDS_PAYMENT")
    if disbursed > paid - refunded:
        reasons.append("PAYOUT_EXCEEDS_NET_RECEIPTS")
    if any(x["state"] == "failed" for x in o):
        reasons.append("FAILED_PAYOUT_REVIEW_REQUIRED")
    if any(x["state"] == "pending" for x in o):
        reasons.append("PENDING_PAYOUT_REVIEW_REQUIRED")
    if not trusted_evidence_verified:
        reasons.append("TRUSTED_EVIDENCE_MISSING")
    if not policy_approved:
        reasons.append("APPROVED_POLICY_MISSING")
    reasons = sorted(set(reasons))
    return {
        "booking_id": booking_id,
        "status": "HOLD" if reasons else "MATCHED_REVIEW_ONLY",
        "payout_hold_required": bool(reasons),
        "payout_execution_enabled": False,
        "operating_db_connected": False,
        "real_payment_enabled": False,
        "gross_krw": paid,
        "refund_krw": refunded,
        "disbursed_krw": disbursed,
        "unsettled_krw": paid - refunded - disbursed,
        "reasons": reasons,
    }
