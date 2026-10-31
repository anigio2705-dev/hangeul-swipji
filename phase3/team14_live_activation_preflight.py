"""#130: offline-only approval-evidence preflight; never activates real money.

This module is intentionally not an approval authority. Every supplied record
is untrusted input, including claimed_approved=True. A production adapter must
independently verify representative authorization, external reviews, signatures,
revocation, provider configuration and environment before *any* live enablement.
There is NO live enable operation in this module.
"""
from datetime import datetime
import re

_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_REQUIRED = frozenset({
    "owner_approval", "provider_review", "legal_tax_review",
    "payout_compliance", "security_qa", "reconciliation_qa",
})
_FIELDS = frozenset({
    "kind", "evidence_id", "scope", "issuer", "issued_at",
    "expires_at", "claimed_approved",
})
_MAX_EVIDENCE = 32


def _valid_id(value):
    return type(value) is str and _ID.fullmatch(value) is not None


def _utc(value):
    if type(value) is not str or len(value) > 40 or not value.endswith("Z"):
        raise ValueError("timestamp must be explicit UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    if parsed.utcoffset().total_seconds() != 0:
        raise ValueError("timestamp must be UTC")
    return parsed


def review_activation_evidence(*, environment, scope, evidence, now_utc):
    """Return an offline preflight report, NEVER authorization to turn money on.

    An all-green fixture produces REVIEW_ONLY, not LIVE_READY. This prevents
    caller-controlled booleans, self-signed claims, or a stale approval from
    enabling live charge, payout, reconciliation, or database changes.
    """
    if environment not in ("sandbox", "production") or type(environment) is not str:
        raise ValueError("invalid environment")
    if not _valid_id(scope):
        raise ValueError("invalid scope")
    now = _utc(now_utc)
    if type(evidence) is not list or len(evidence) > _MAX_EVIDENCE:
        raise ValueError("invalid evidence list")

    blockers = set()
    seen_ids = set()
    seen_kinds = set()
    valid_kinds = set()
    for record in evidence:
        if type(record) is not dict or frozenset(record) != _FIELDS:
            raise ValueError("invalid approval record schema")
        kind = record["kind"]
        if type(kind) is not str or kind not in _REQUIRED:
            raise ValueError("unknown approval kind")
        for field in ("evidence_id", "scope", "issuer"):
            if not _valid_id(record[field]):
                raise ValueError("invalid approval identifier")
        if type(record["claimed_approved"]) is not bool:
            raise ValueError("claimed approval must be bool")
        issued = _utc(record["issued_at"])
        expires = _utc(record["expires_at"])
        if record["evidence_id"] in seen_ids:
            blockers.add("DUPLICATE_EVIDENCE_ID")
        if kind in seen_kinds:
            blockers.add("DUPLICATE_APPROVAL_KIND")
        seen_ids.add(record["evidence_id"])
        seen_kinds.add(kind)
        if record["scope"] != scope:
            blockers.add("SCOPE_MISMATCH")
        if issued > now:
            blockers.add("FUTURE_DATED_EVIDENCE")
        if expires <= issued or expires <= now:
            blockers.add("EXPIRED_OR_INVALID_EVIDENCE")
        if not record["claimed_approved"]:
            blockers.add("UNAPPROVED_EVIDENCE")
        if (record["scope"] == scope and issued <= now < expires
                and record["claimed_approved"]):
            valid_kinds.add(kind)

    missing = sorted(_REQUIRED - valid_kinds)
    if missing:
        blockers.add("REQUIRED_APPROVALS_MISSING")
    # No supplied evidence can prove its own origin, signature or revocation.
    blockers.add("TRUSTED_ATTESTATION_VERIFIER_NOT_CONNECTED")
    blockers.add("LIVE_PROVIDER_AND_LEDGER_ADAPTER_NOT_CONNECTED")
    blockers.add("EXPLICIT_OWNER_LIVE_RELEASE_NOT_VERIFIED")
    return {
        "scope": scope,
        "environment": environment,
        "decision": "HOLD" if len(blockers) > 3 else "REVIEW_ONLY",
        "missing_approval_kinds": missing,
        "blockers": sorted(blockers),
        "evidence_count": len(evidence),
        "evidence_untrusted": True,
        "can_enable_real_charge": False,
        "can_enable_real_payout": False,
        "can_enable_real_settlement": False,
        "can_change_operating_db": False,
        "can_deploy_to_production": False,
        "live_activation_performed": False,
    }
