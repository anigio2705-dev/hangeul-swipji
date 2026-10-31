"""#107 country-by-country referral compliance *review* gate.

This is a pure, fail-closed product boundary, not legal/tax advice or a
source of approval. Evidence supplied by callers is NOT authenticated here.
No result from this module can authorize live credits, transfers or payouts.
"""

import re

COUNTRIES = {
    "KR": "South Korea", "US": "United States", "JP": "Japan",
    "CN": "China", "ES": "Spain", "RU": "Russia",
    "MN": "Mongolia", "VN": "Vietnam",
}
REWARD_KINDS = frozenset({"discount", "points", "cash_equivalent", "cash_payout"})


def _nonnegative_int(value):
    return type(value) is int and value >= 0


def _evidence_complete(evidence, *, country_code, reward_kind, depth, as_of):
    """Only checks *shape/completeness*; never verifies signatures or law."""
    if evidence is None:
        return False
    if type(evidence) is not dict:
        raise ValueError("review_evidence must be a dict or None")
    issued = evidence.get("reviewed_at")
    expires = evidence.get("expires_at")
    maximum = evidence.get("max_referral_depth")
    kinds = evidence.get("reviewed_reward_kinds")
    reference = evidence.get("review_reference")
    version = evidence.get("policy_version")
    return bool(
        evidence.get("country_code") == country_code
        and evidence.get("legal_reviewed") is True
        and evidence.get("tax_reviewed") is True
        and _nonnegative_int(issued)
        and _nonnegative_int(expires)
        and issued <= as_of < expires
        and type(maximum) is int and 1 <= depth <= maximum <= 10
        and type(kinds) in (list, tuple)
        and len(kinds) <= len(REWARD_KINDS)
        and all(type(kind) is str and kind in REWARD_KINDS for kind in kinds)
        and reward_kind in kinds
        and type(reference) is str and 6 <= len(reference) <= 160
        and type(version) is str and re.fullmatch(r"[A-Za-z0-9._-]{1,40}", version)
    )


def evaluate_country_referral(*, country_code, reward_kind, referral_depth,
                              as_of, review_evidence=None):
    """Return a read-only review status; always deny real-money activation.

    The optional evidence record is caller-provided and unverified. Even a
    complete record requires independent legal/tax validation and an explicit
    owner-approved, separately authenticated server-side policy gate.
    """
    if type(country_code) is not str or not re.fullmatch(r"[A-Z]{2}", country_code):
        raise ValueError("country_code must be a two-letter uppercase code")
    if type(reward_kind) is not str or reward_kind not in REWARD_KINDS:
        raise ValueError("unknown reward kind")
    if type(referral_depth) is not int or not 1 <= referral_depth <= 10:
        raise ValueError("referral_depth must be an integer from 1 to 10")
    if not _nonnegative_int(as_of):
        raise ValueError("as_of must be a nonnegative integer Unix timestamp")

    evidence_complete = _evidence_complete(
        review_evidence, country_code=country_code, reward_kind=reward_kind,
        depth=referral_depth, as_of=as_of,
    )
    if country_code not in COUNTRIES:
        status = "UNSUPPORTED_COUNTRY"
    elif evidence_complete:
        status = "EVIDENCE_UNVERIFIED_OWNER_DECISION_REQUIRED"
    else:
        status = "LEGAL_TAX_REVIEW_REQUIRED"

    warnings = ["COUNTRY_SPECIFIC_LEGAL_AND_TAX_REVIEW_REQUIRED"]
    if referral_depth > 1:
        warnings.append("MULTI_LEVEL_REWARD_RISK")
    if reward_kind in {"cash_equivalent", "cash_payout"}:
        warnings.append("CASH_EQUIVALENT_OR_PAYOUT_RISK")

    return {
        "country_code": country_code,
        "country_name": COUNTRIES.get(country_code, "Unsupported"),
        "reward_kind": reward_kind,
        "referral_depth": referral_depth,
        "status": status,
        "review_evidence_complete_unverified": evidence_complete,
        "warnings": warnings,
        "owner_approval_required": True,
        "policy_approved": False,
        "real_money": False,
        "payment_enabled": False,
        "cash_payout_enabled": False,
        "can_activate": False,
    }
