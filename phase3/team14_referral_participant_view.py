"""#110 follow-up: isolated per-participant explanation of a reward simulation.

This is a pure, nonbinding projection, NOT an authentication endpoint. A future
server adapter must obtain the principal, booking and role roster from trusted
server-side sessions/database, never from request JSON. No policy is approved
by this module. No payment, points, payout, database or HTTP integration.
"""
import hmac
import html
import re

from team14_referral_policy_preview import (
    REASONS, CANCELLATION_CONDITIONS, MAX_KRW,
)

ROLES = ("learner", "teacher", "referrer", "platform")
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
VERSION = re.compile(r"[A-Za-z0-9._-]{1,64}\Z")
SAFETY_FLAGS = (
    "real_money", "payment_enabled", "points_credited",
    "payout_authorized", "production_policy_activated",
)
ROLE_TEXT = {
    "learner": "소개 보상은 학습·예약 자격과 별개이며, 가상 보상 금액은 표시되지 않습니다.",
    "teacher": "강사 보수와 수업 이행은 이 소개 보상 검토로 변경되지 않습니다.",
    "referrer": "소개 보상은 승인된 실제 정책이 아니라 검증 대상 가상 후보입니다.",
    "platform": "가상 후보는 정산 원장·지급·포인트에 반영되지 않습니다.",
}


def _id(value):
    return type(value) is str and IDENTIFIER.fullmatch(value) is not None


def project_participant_view(*, simulation, role, authenticated_actor_id,
                             trusted_roster, booking_evidence_verified):
    """Project one participant's view; trusted_* inputs MUST be server sourced.

    This is an internal adapter contract, not proof that caller authentication
    or real-world policy approval has occurred. All flags remain nonbinding.
    """
    if role not in ROLES or type(role) is not str:
        raise ValueError("unknown role")
    if type(trusted_roster) is not dict or set(trusted_roster) != set(ROLES):
        raise ValueError("exact trusted roster required")
    if not all(_id(v) for v in trusted_roster.values()):
        raise ValueError("invalid trusted roster identifier")
    if len(set(trusted_roster.values())) != len(ROLES):
        raise ValueError("conflicting participant identities")
    if not _id(authenticated_actor_id) or not hmac.compare_digest(
            authenticated_actor_id, trusted_roster[role]):
        raise PermissionError("actor does not own requested participant view")
    if type(booking_evidence_verified) is not bool:
        raise ValueError("booking evidence must be a server verified boolean")
    if type(simulation) is not dict:
        raise ValueError("simulation result required")
    required = {
        "policy_version", "approval_evidence_verified", "state",
        "hypothetical_referral_candidate_krw", *SAFETY_FLAGS,
    }
    if not required.issubset(simulation):
        raise ValueError("simulation schema missing safety fields")
    if type(simulation["policy_version"]) is not str or not VERSION.fullmatch(
            simulation["policy_version"]):
        raise ValueError("invalid policy version")
    if type(simulation["state"]) is not str or simulation["state"] not in REASONS:
        raise ValueError("unknown simulation state")
    if type(simulation["approval_evidence_verified"]) is not bool:
        raise ValueError("invalid policy evidence flag")
    amount = simulation["hypothetical_referral_candidate_krw"]
    if type(amount) is not int or not 0 <= amount <= MAX_KRW:
        raise ValueError("invalid simulated amount")
    if any(simulation[flag] is not False for flag in SAFETY_FLAGS):
        raise ValueError("live money or activation must remain disabled")
    if simulation["state"] != "SIMULATED_CANDIDATE" and amount:
        raise ValueError("noncandidate state cannot carry money")
    if not booking_evidence_verified:
        state = "BOOKING_UNVERIFIED"
        reason = "서버에서 예약·참여자 증거를 확인하지 못해 가상 후보를 표시하지 않습니다."
    elif not simulation["approval_evidence_verified"]:
        state = "POLICY_UNVERIFIED"
        reason = REASONS[state]
    else:
        state = simulation["state"]
        reason = REASONS[state]
    visible_amount = (amount if role == "referrer" and
                      state == "SIMULATED_CANDIDATE" else None)
    return {
        "role": role,
        "policy_version": simulation["policy_version"],
        "state": state,
        "reason": reason,
        "participant_explanation": ROLE_TEXT[role],
        "cancellation_conditions": list(CANCELLATION_CONDITIONS),
        "hypothetical_candidate_krw": visible_amount,
        "nonbinding": True,
        "live_payment_enabled": False,
        "live_payout_enabled": False,
        "operating_db_connected": False,
        "production_policy_activated": False,
    }


def render_participant_html(view):
    """Accessible static HTML fragment; no browser auth, controls or network."""
    if type(view) is not dict or view.get("role") not in ROLES:
        raise ValueError("invalid participant view")
    if view.get("nonbinding") is not True or any(view.get(k) is not False for k in
        ("live_payment_enabled", "live_payout_enabled",
         "operating_db_connected", "production_policy_activated")):
        raise ValueError("only nonbinding views can be rendered")
    esc = lambda value: html.escape(str(value), quote=True)
    conditions = view.get("cancellation_conditions")
    if type(conditions) is not list or not all(type(s) is str and len(s) < 300
                                               for s in conditions):
        raise ValueError("invalid cancellation conditions")
    amount = view.get("hypothetical_candidate_krw")
    if amount is not None and (view["role"] != "referrer" or
                               type(amount) is not int or amount < 0):
        raise ValueError("unauthorized amount display")
    amount_html = ("<p>가상 후보 금액: " + esc(amount) + "원 (지급 아님)</p>"
                   if amount is not None else "")
    return ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; '
            'base-uri &#39;none&#39;; form-action &#39;none&#39;">'
            '<title>한글쉽지 보상 설명 (격리 검토)</title></head><body><main>'
            '<h1>참여자별 가상 보상 설명</h1>'
            '<p role="status">정책 미승인 · 실제 지급 불가 · 읽기 전용</p>'
            '<p>참여자 역할: ' + esc(view["role"]) + '</p>'
            '<p>모의 버전: ' + esc(view["policy_version"]) + '</p>'
            '<p>상태: ' + esc(view["state"]) + '</p>'
            '<p>사유: ' + esc(view["reason"]) + '</p>'
            '<p>' + esc(view["participant_explanation"]) + '</p>'
            + amount_html + '<h2>취소·보류 조건</h2><ul>' +
            ''.join('<li>' + esc(s) + '</li>' for s in conditions) +
            '</ul></main></body></html>')
