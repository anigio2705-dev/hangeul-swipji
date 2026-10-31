"""#126: teacher payout/KYC/tax/country verification *procedure*, not verification.

No bank details, identity document, tax identifier or real payout is collected.
All supplied evidence is untrusted until an external provider and authorized
reviewer validate it. A complete mock checklist is never payout permission.
"""
from datetime import datetime
import re

_STAGES = (
    "identity_verification",
    "recipient_ownership",
    "tax_requirements",
    "country_eligibility",
    "provider_payout_capability",
)
_FIELDS = frozenset({
    "stage", "evidence_ref", "reviewer_ref", "checked_at",
    "expires_at", "claimed_pass",
})
_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
_COUNTRY = re.compile(r"[A-Z]{2}")


def _id(value):
    return type(value) is str and _ID.fullmatch(value) is not None


def _utc(value):
    if type(value) is not str or len(value) > 40 or not value.endswith("Z"):
        raise ValueError("explicit UTC timestamp required")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("invalid UTC timestamp") from exc


def review_teacher_payout_procedure(*, teacher_ref, country_code, evidence, as_of_utc):
    """Prepare a privacy-minimal review checklist, NEVER a payout authorization."""
    if not _id(teacher_ref):
        raise ValueError("invalid teacher reference")
    if type(country_code) is not str or _COUNTRY.fullmatch(country_code) is None:
        raise ValueError("invalid country code format")
    now = _utc(as_of_utc)
    if type(evidence) is not list or len(evidence) > 10:
        raise ValueError("invalid evidence list")
    reasons = set()
    observed = set()
    passed = set()
    for item in evidence:
        if type(item) is not dict or frozenset(item) != _FIELDS:
            raise ValueError("invalid review record schema; raw sensitive data forbidden")
        stage = item["stage"]
        if type(stage) is not str or stage not in _STAGES:
            raise ValueError("invalid review stage")
        if not _id(item["evidence_ref"]) or not _id(item["reviewer_ref"]):
            raise ValueError("invalid evidence/reviewer reference")
        if type(item["claimed_pass"]) is not bool:
            raise ValueError("claimed_pass must be boolean")
        checked, expires = _utc(item["checked_at"]), _utc(item["expires_at"])
        if stage in observed:
            reasons.add("DUPLICATE_REVIEW_STAGE")
        observed.add(stage)
        if checked > now:
            reasons.add("FUTURE_DATED_REVIEW")
        if expires <= checked or expires <= now:
            reasons.add("STALE_OR_INVALID_REVIEW")
        if not item["claimed_pass"]:
            reasons.add("REVIEW_NOT_PASSED")
        if checked <= now < expires and item["claimed_pass"]:
            passed.add(stage)

    missing = [stage for stage in _STAGES if stage not in passed]
    if missing:
        reasons.add("REQUIRED_VERIFICATIONS_MISSING")
    # An ISO-shaped code is NOT proof of supported payout jurisdiction.
    reasons.add("COUNTRY_AND_CURRENCY_PROVIDER_CONFIRMATION_REQUIRED")
    reasons.add("TRUSTED_KYC_TAX_PROVIDER_AND_REVIEWER_NOT_CONNECTED")
    reasons.add("REPRESENTATIVE_PAYOUT_APPROVAL_NOT_VERIFIED")
    return {
        "teacher_ref": teacher_ref,
        "country_code_unverified": country_code,
        "procedure_steps": list(_STAGES),
        "missing_stages": missing,
        "reasons": sorted(reasons),
        "review_status": "REVIEW_ONLY" if len(reasons) == 3 else "HOLD",
        "evidence_untrusted": True,
        "collect_raw_bank_or_identity_data": False,
        "tax_decision_made": False,
        "country_payout_supported": False,
        "recipient_verified": False,
        "can_payout": False,
        "can_activate_real_money": False,
        "operating_db_connected": False,
    }
