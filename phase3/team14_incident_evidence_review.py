"""#112 evidence-first dispute triage for lesson nonperformance, connection and quality.

Pure, read-only review contract. The caller MUST be a trusted server adapter that
authenticates parties and verifies evidence against stored records. A client-supplied
"verified" flag is not proof. This module never resolves fault, refunds or payouts.
"""
from datetime import datetime, timezone

CATEGORIES = frozenset({"nonperformance", "connectivity", "quality"})
EVIDENCE_TYPES = frozenset({"booking", "attendance", "session", "connection_log", "feedback", "incident"})
REQUIRED = {
    "nonperformance": frozenset({"booking", "attendance", "session"}),
    "connectivity": frozenset({"booking", "connection_log", "session"}),
    "quality": frozenset({"booking", "session", "feedback"}),
}
EXPLANATIONS = {
    "nonperformance": "예약·출석·수업 기록을 대조한 후 양측 확인이 필요합니다.",
    "connectivity": "연결 로그와 실제 입장 기록을 확인하고 양측의 장애 설명을 받습니다.",
    "quality": "품질 불만과 수업 기록을 분리하여 양측 의견을 검토합니다.",
}
MAX_TIMESTAMP = 4102444800


def _identifier(value, label):
    if type(value) is not str or not 1 <= len(value) <= 128 or not all(
        ch.isascii() and (ch.isalnum() or ch in "_-") for ch in value
    ):
        raise ValueError("invalid " + label)
    return value


def _timestamp(value, label):
    if type(value) is not int or not 0 <= value <= MAX_TIMESTAMP:
        raise ValueError("invalid " + label)
    return value


def review_incident(*, incident_id, booking_id, category, occurred_at, as_of,
                    evidence=(), learner_statement_received=False,
                    teacher_statement_received=False):
    """Triage verified server evidence and party response presence only.

    evidence: sequence of server-verified {kind, reference, captured_at} records.
    No statement text, IP address or sensitive content is accepted or returned.
    The caller must authenticate both parties and verify each reference in its DB.
    """
    _identifier(incident_id, "incident_id")
    _identifier(booking_id, "booking_id")
    if type(category) is not str or category not in CATEGORIES:
        raise ValueError("invalid incident category")
    _timestamp(occurred_at, "occurred_at")
    _timestamp(as_of, "as_of")
    if occurred_at > as_of:
        raise ValueError("incident is in the future")
    if type(learner_statement_received) is not bool or type(teacher_statement_received) is not bool:
        raise ValueError("invalid statement receipt flag")
    if type(evidence) not in (tuple, list) or len(evidence) > 20:
        raise ValueError("invalid evidence sequence")
    kinds = set()
    references = set()
    for item in evidence:
        if type(item) is not dict or set(item) != {"kind", "reference", "captured_at"}:
            raise ValueError("invalid evidence record")
        kind = item["kind"]
        if type(kind) is not str or kind not in EVIDENCE_TYPES:
            raise ValueError("invalid evidence type")
        reference = _identifier(item["reference"], "evidence reference")
        captured_at = _timestamp(item["captured_at"], "evidence captured_at")
        if captured_at > as_of:
            raise ValueError("future evidence cannot be used")
        if reference in references:
            raise ValueError("duplicate evidence reference")
        kinds.add(kind)
        references.add(reference)
    missing = sorted(REQUIRED[category] - kinds)
    missing_statements = [
        party for party, received in (
            ("learner", learner_statement_received),
            ("teacher", teacher_statement_received),
        ) if not received
    ]
    if missing:
        state = "WAIT_EVIDENCE"
    elif missing_statements:
        state = "WAIT_PARTY_STATEMENTS"
    else:
        state = "MANUAL_REVIEW"
    return {
        "incident_id": incident_id,
        "booking_id": booking_id,
        "category": category,
        "review_state": state,
        "required_evidence": sorted(REQUIRED[category]),
        "missing_evidence": missing,
        "missing_party_statements": missing_statements,
        "evidence_reference_count": len(references),
        "explanation": EXPLANATIONS[category],
        "decision_maker": "authorized_human_reviewer",
        "automatic_fault_assigned": False,
        "refund_authorized": False,
        "penalty_authorized": False,
        "payment_enabled": False,
        "real_money": False,
        "booking_mutated": False,
        "policy_approved": False,
    }


def incident_matrix():
    """Three distinct evidence/confirmation tracks; no automatic judgments."""
    return tuple({
        "category": category,
        "required_evidence": sorted(REQUIRED[category]),
        "requires_both_party_statements": True,
        "resolution": "HUMAN_REVIEW_ONLY",
    } for category in ("nonperformance", "connectivity", "quality"))
