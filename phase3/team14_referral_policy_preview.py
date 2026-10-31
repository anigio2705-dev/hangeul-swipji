"""#110: versioned referral reward *simulation* behind verified policy evidence.

This module is deliberately detached from HTTP, DB, checkout and payouts.
A caller MUST obtain the HMAC key and event evidence from a trusted server;
never accept a key, signed policy, or event evidence from a browser request.
No real policy is configured or approved in this module.
"""

import hashlib
import hmac
import json
import re

MAX_KRW = 10**12
MAX_TIME = 4102444800  # 2100-01-01 UTC
POLICY_FIELDS = frozenset({
    "version", "rate_bps", "cap_krw", "effective_from", "expires_at",
    "refund_window_seconds", "approved_by", "scope",
})
REASONS = {
    "POLICY_UNVERIFIED": "승인된 정책 버전과 서명 증빙이 확인되지 않았습니다.",
    "POLICY_NOT_EFFECTIVE": "해당 시점에 적용 가능한 정책 버전이 아닙니다.",
    "REFUND_VOID": "환불·취소 기록으로 소개 보상 후보가 취소되었습니다.",
    "RISK_REVIEW": "소개 관계 또는 거래 증거에 독립 검토가 필요합니다.",
    "REFERRER_INELIGIBLE": "추천인의 현재 자격이 충족되지 않아 신규 보상이 없습니다.",
    "WAIT_PAYMENT": "결제 확인 전에는 보상 후보를 계산하지 않습니다.",
    "WAIT_LESSON": "수업 완료와 출석 확인을 기다립니다.",
    "WAIT_REFUND_WINDOW": "환불 가능 기간이 종료되기 전에는 확정 후보가 없습니다.",
    "SIMULATED_CANDIDATE": "검증된 정책 버전에 따른 가상 후보이며 실제 지급이 아닙니다.",
}
CANCELLATION_CONDITIONS = (
    "환불·취소·차지백 발생 시 후보 무효",
    "결제 또는 수업·출석 증빙 취소 시 재검토",
    "추천인 자격 상실 시 신규 보상 후보 제외",
    "자기추천·순환소개·가짜 거래 등 위험 신호 발견 시 보류",
    "정책 유효기간·국가별 법률·세무 승인 범위 밖에서는 적용 금지",
)


def _integer(value, name, maximum):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f"{name} must be a bounded nonnegative integer")
    return value


def _bool(value, name):
    if type(value) is not bool:
        raise ValueError(f"{name} must be boolean")
    return value


def _validate_policy(record):
    if type(record) is not dict or set(record) != POLICY_FIELDS:
        raise ValueError("policy schema mismatch")
    if type(record["version"]) is not str or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", record["version"]):
        raise ValueError("invalid version")
    if type(record["approved_by"]) is not str or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", record["approved_by"]):
        raise ValueError("invalid approval identity")
    if record["scope"] != "referral_simulation_only":
        raise ValueError("real-money policy scope forbidden")
    _integer(record["rate_bps"], "rate_bps", 10000)
    _integer(record["cap_krw"], "cap_krw", MAX_KRW)
    start = _integer(record["effective_from"], "effective_from", MAX_TIME)
    end = _integer(record["expires_at"], "expires_at", MAX_TIME)
    if end <= start:
        raise ValueError("invalid policy effective period")
    _integer(record["refund_window_seconds"], "refund_window_seconds", 90 * 86400)
    return record


def canonical_policy_bytes(record):
    """Stable bytes for trusted offline approval/signature workflow."""
    _validate_policy(record)
    return json.dumps(record, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


def _signature_valid(record, signature, verification_key):
    if type(signature) is not str or not re.fullmatch(r"[0-9a-f]{64}", signature):
        return False
    if type(verification_key) is not bytes or len(verification_key) < 32:
        return False
    expected = hmac.new(verification_key, canonical_policy_bytes(record),
                        hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def simulate_versioned_reward(*, policy_version, policy_record=None,
                              approval_signature=None, trusted_verification_key=None,
                              gross_krw, payment_verified, lesson_completed,
                              attendance_verified, refunded, referrer_eligible,
                              risk_flags=(), paid_at=None, completed_at=None, as_of):
    """Explain hypothetical reward candidate; NEVER credit, pay, or approve.

    No key/policy is shipped with the app. Only trusted server configuration
    may supply signed policy evidence and verified booking/referral facts.
    """
    if type(policy_version) is not str or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", policy_version):
        raise ValueError("invalid requested policy version")
    gross_krw = _integer(gross_krw, "gross_krw", MAX_KRW)
    as_of = _integer(as_of, "as_of", MAX_TIME)
    for name, value in (("payment_verified", payment_verified),
                        ("lesson_completed", lesson_completed),
                        ("attendance_verified", attendance_verified),
                        ("refunded", refunded),
                        ("referrer_eligible", referrer_eligible)):
        _bool(value, name)
    if type(risk_flags) not in (list, tuple) or len(risk_flags) > 100:
        raise ValueError("bounded server risk flags required")
    for flag in risk_flags:
        if type(flag) is not str or not re.fullmatch(r"[A-Z_]{1,64}", flag):
            raise ValueError("invalid risk flag")
    for name, value in (("paid_at", paid_at), ("completed_at", completed_at)):
        if value is not None:
            _integer(value, name, MAX_TIME)
    if payment_verified and paid_at is None:
        raise ValueError("verified payment timestamp required")
    if lesson_completed and completed_at is None:
        raise ValueError("completed lesson timestamp required")
    if paid_at is not None and paid_at > as_of and payment_verified:
        raise ValueError("future payment cannot be verified")
    if completed_at is not None and completed_at > as_of and lesson_completed:
        raise ValueError("future lesson cannot be verified")

    valid = False
    record = None
    if policy_record is not None:
        record = _validate_policy(policy_record)
        valid = (record["version"] == policy_version and
                 _signature_valid(record, approval_signature, trusted_verification_key))

    if not valid:
        state = "POLICY_UNVERIFIED"
    elif not record["effective_from"] <= as_of < record["expires_at"]:
        state = "POLICY_NOT_EFFECTIVE"
    elif refunded:
        state = "REFUND_VOID"
    elif risk_flags:
        state = "RISK_REVIEW"
    elif not referrer_eligible:
        state = "REFERRER_INELIGIBLE"
    elif not payment_verified:
        state = "WAIT_PAYMENT"
    elif not lesson_completed or not attendance_verified:
        state = "WAIT_LESSON"
    elif as_of < max(paid_at, completed_at) + record["refund_window_seconds"]:
        state = "WAIT_REFUND_WINDOW"
    else:
        state = "SIMULATED_CANDIDATE"

    candidate = (min(gross_krw * record["rate_bps"] // 10000, record["cap_krw"])
                 if state == "SIMULATED_CANDIDATE" else 0)
    return {
        "policy_version": policy_version,
        "approval_evidence_verified": valid,
        "state": state,
        "reason": REASONS[state],
        "cancellation_conditions": list(CANCELLATION_CONDITIONS),
        "participants": {
            "learner": "학습·예약은 보상 후보와 독립적입니다.",
            "teacher": "강사 보수·수업 이행은 이 가상 계산으로 변경되지 않습니다.",
            "referrer": REASONS[state],
            "platform": "가상 소개 보상 후보만 계산하며 회계·정산 원장은 변경하지 않습니다.",
        },
        "hypothetical_referral_candidate_krw": candidate,
        "real_money": False,
        "payment_enabled": False,
        "points_credited": False,
        "payout_authorized": False,
        "production_policy_activated": False,
    }
