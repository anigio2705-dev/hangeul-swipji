"""#129: safe, deterministic transaction/receipt/teacher-income document previews.

No provider, payment, tax filing, document issuance, DB, email or network.
Inputs are caller-supplied and are NOT proof of authenticated transactions.
Production adapters must verify the actor, provider events, policies and ledger.
"""
from copy import deepcopy
from hashlib import sha256
import json
import re

from team14_reconciliation_review import reconcile_booking

_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_COUNTRY = re.compile(r"[A-Z]{2}\Z")
_MAX_KRW = 10 ** 12


def _identity(value):
    return type(value) is str and _ID.fullmatch(value) is not None


def _krw(value):
    return type(value) is int and 0 <= value <= _MAX_KRW


def _document_id(kind, values):
    payload = json.dumps([kind, values], ensure_ascii=True, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return "preview_" + sha256(payload).hexdigest()[:24]


def build_document_bundle(*, booking_id, learner_id, teacher_id, country_code,
                          payments, refunds, ledger, payouts,
                          platform_fee_krw, referral_fee_krw,
                          trusted_evidence_verified=False, policy_approved=False):
    """Build read-only document structures; never issue an official receipt.

    Uses the #128 reconciliation implementation, not caller-supplied
    reconciliation status. Boolean verification flags remain UNTRUSTED until
    an authenticated server/provider adapter independently establishes them.
    """
    if not all(_identity(x) for x in (booking_id, learner_id, teacher_id)):
        raise ValueError("invalid actor or booking identity")
    if learner_id == teacher_id:
        raise ValueError("learner and teacher identities must differ")
    if type(country_code) is not str or _COUNTRY.fullmatch(country_code) is None:
        raise ValueError("invalid country code")
    if not _krw(platform_fee_krw) or not _krw(referral_fee_krw):
        raise ValueError("invalid fee amount")

    result = reconcile_booking(
        booking_id=booking_id, payments=payments, refunds=refunds,
        ledger=ledger, payouts=payouts,
        trusted_evidence_verified=trusted_evidence_verified,
        policy_approved=policy_approved)
    gross = result["gross_krw"]
    refunded = result["refund_krw"]
    disbursed = result["disbursed_krw"]
    net = gross - refunded
    teacher_due = net - platform_fee_krw - referral_fee_krw
    reasons = list(result["reasons"])
    if teacher_due < 0:
        reasons.append("FEES_EXCEED_NET_RECEIPTS")
    if disbursed > max(0, teacher_due):
        reasons.append("TEACHER_PAYOUT_EXCEEDS_DUE")
    reasons = sorted(set(reasons))

    common = {
        "booking_id": booking_id,
        "currency": "KRW",
        "gross_krw": gross,
        "refunded_krw": refunded,
        "net_receipts_krw": net,
    }
    transaction = {
        "document_id": _document_id("transaction", common),
        "kind": "TRANSACTION_STATEMENT_PREVIEW",
        **common,
        "status": "PREVIEW_ONLY_NOT_ISSUED",
    }
    receipt = {
        "document_id": _document_id("receipt", common),
        "kind": "PAYMENT_RECEIPT_PREVIEW",
        **common,
        "status": "NOT_A_FISCAL_OR_PROVIDER_RECEIPT",
        "provider_receipt_reference": None,
    }
    teacher_base = {
        "booking_id": booking_id,
        "currency": "KRW",
        "teacher_id": teacher_id,
        "net_receipts_krw": net,
        "platform_fee_krw": platform_fee_krw,
        "referral_fee_krw": referral_fee_krw,
        "teacher_due_krw": max(0, teacher_due),
        "already_disbursed_krw": disbursed,
        "remaining_due_krw": max(0, teacher_due - disbursed),
    }
    settlement = {
        "document_id": _document_id("settlement", teacher_base),
        "kind": "TEACHER_SETTLEMENT_PREVIEW",
        **teacher_base,
        "status": "PREVIEW_ONLY_NOT_PAYABLE",
    }
    income = {
        "document_id": _document_id("income", teacher_base),
        "kind": "INCOME_SUPPORT_DATA_PREVIEW",
        "booking_id": booking_id,
        "teacher_id": teacher_id,
        "country_code": country_code,
        "currency": "KRW",
        "gross_teacher_due_krw": max(0, teacher_due),
        "already_disbursed_krw": disbursed,
        "tax_treatment": "UNDETERMINED_REQUIRES_EXTERNAL_REVIEW",
        "withholding_krw": None,
        "status": "NOT_A_TAX_CERTIFICATE",
    }
    return {
        "booking_id": booking_id,
        "learner_id": learner_id,
        "teacher_id": teacher_id,
        "status": "HOLD" if reasons else "PREVIEW_ONLY",
        "reasons": reasons,
        "documents": {
            "transaction_statement": transaction,
            "receipt_preview": receipt,
            "teacher_settlement": settlement,
            "income_support_data": income,
        },
        "provider_connected": False,
        "operating_db_connected": False,
        "official_document_issued": False,
        "real_payment_enabled": False,
        "real_payout_enabled": False,
        "tax_filing_enabled": False,
    }


def view_for_role(bundle, *, actor_id, role):
    """Least-privilege preview, never expose the other party's document.

    This is NOT authentication: the caller must obtain actor_id and role from
    a verified server session, never a client-supplied claim.
    """
    if type(bundle) is not dict or type(role) is not str or not _identity(actor_id):
        raise ValueError("invalid document view request")
    if role == "learner" and actor_id == bundle.get("learner_id"):
        keys = ("transaction_statement", "receipt_preview")
    elif role == "teacher" and actor_id == bundle.get("teacher_id"):
        keys = ("teacher_settlement", "income_support_data")
    else:
        raise PermissionError("document actor or role not authorized")
    docs = bundle.get("documents")
    if type(docs) is not dict or any(k not in docs for k in keys):
        raise ValueError("invalid document bundle")
    return {
        "status": bundle.get("status"),
        "reasons": deepcopy(bundle.get("reasons")),
        "documents": {k: deepcopy(docs[k]) for k in keys},
        "official_document_issued": False,
        "real_payment_enabled": False,
        "real_payout_enabled": False,
    }
