"""#111 non-monetary single/monthly lesson disruption review matrix.

No refund amount, penalty, booking mutation, live policy or payment operation.
Events/evidence must be sourced from trusted server records, not the client.
"""

KINDS = frozenset({"single", "monthly"})
ACTORS = frozenset({"learner", "teacher", "system"})
EVENTS = frozenset({"cancel", "no_show", "late", "early_end"})
EVIDENCE = frozenset({"booking", "notice", "attendance", "session", "incident"})
REQUIRED = {
    "cancel": ("booking", "notice"),
    "no_show": ("booking", "attendance"),
    "late": ("booking", "attendance", "session"),
    "early_end": ("booking", "attendance", "session"),
}
REASONS = {
    "cancel": "수업 취소 시점과 통지·책임 주체를 검토해야 합니다.",
    "no_show": "예약 시간과 출석 기록을 대조해 노쇼 여부를 검토해야 합니다.",
    "late": "입장 시각·지각 시간·상대방 대기 증거를 확인해야 합니다.",
    "early_end": "실제 수업 시간·중도 종료 사유·양측 기록을 검토해야 합니다.",
}


def review_disruption(*, lesson_kind, actor, event_kind, booking_id,
                      scheduled_at, observed_at, evidence_keys=(),
                      monthly_lesson_index=None):
    """Return a review-only case, not an automated refund/penalty decision."""
    if type(lesson_kind) is not str or lesson_kind not in KINDS:
        raise ValueError("invalid lesson kind")
    if type(actor) is not str or actor not in ACTORS:
        raise ValueError("invalid actor")
    if type(event_kind) is not str or event_kind not in EVENTS:
        raise ValueError("invalid disruption event")
    if type(booking_id) is not str or not booking_id or len(booking_id) > 128 or not all(
            c.isascii() and (c.isalnum() or c in "_-") for c in booking_id):
        raise ValueError("invalid booking identifier")
    for name, val in (("scheduled_at", scheduled_at), ("observed_at", observed_at)):
        if type(val) is not int or not 0 <= val <= 4102444800:
            raise ValueError("invalid " + name)
    if type(evidence_keys) not in (tuple, list) or len(evidence_keys) > 20 or any(
            type(x) is not str or x not in EVIDENCE for x in evidence_keys):
        raise ValueError("invalid trusted evidence list")
    if lesson_kind == "monthly":
        if type(monthly_lesson_index) is not int or not 1 <= monthly_lesson_index <= 366:
            raise ValueError("monthly lesson index required")
    elif monthly_lesson_index is not None:
        raise ValueError("single lesson cannot have monthly index")
    provided = set(evidence_keys)
    missing = sorted(set(REQUIRED[event_kind]) - provided)
    return {
        "lesson_kind": lesson_kind,
        "actor": actor,
        "event_kind": event_kind,
        "booking_id": booking_id,
        "monthly_lesson_index": monthly_lesson_index,
        "notice_before_scheduled": observed_at < scheduled_at,
        "review_state": "MISSING_EVIDENCE" if missing else "MANUAL_POLICY_REVIEW",
        "required_evidence": list(REQUIRED[event_kind]),
        "missing_evidence": missing,
        "explanation": REASONS[event_kind],
        "refund_amount_krw": None,
        "penalty_amount_krw": None,
        "refund_authorized": False,
        "penalty_authorized": False,
        "real_money": False,
        "policy_approved": False,
        "booking_mutated": False,
    }


def case_matrix():
    """24 scenarios; no inferred cancellation fee or refund percentage."""
    return tuple({"lesson_kind": kind, "actor": actor, "event_kind": event,
                  "required_evidence": list(REQUIRED[event]),
                  "refund_policy": "UNAPPROVED_REVIEW_ONLY"}
                 for kind in ("single", "monthly")
                 for actor in ("learner", "teacher", "system")
                 for event in ("cancel", "no_show", "late", "early_end"))
