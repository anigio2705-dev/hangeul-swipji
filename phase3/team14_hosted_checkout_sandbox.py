"""#125: fail-closed sandbox-only hosted-checkout handoff contract.

Pure review component. It NEVER collects card details, creates sessions, sends
HTTP requests, redirects a browser, charges a card or writes a database.
A real provider-hosted checkout must be integrated and independently audited
before this can be used as an actual payment path.
"""
import hmac
import html
import re
from urllib.parse import urlsplit

_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_SESSION_PATH = re.compile(r"/session/(cs_test_[A-Za-z0-9_-]{6,80})\Z")
# Deliberately NON-ROUTABLE test host. Never allow a production checkout host.
_SANDBOX_HOST = "checkout.sandbox.example.invalid"
_FORBIDDEN_FIELDS = frozenset({
    "card", "card_number", "pan", "cvc", "cvv", "expiry",
    "expiration", "exp_month", "exp_year", "security_code",
    "payment_method_data", "billing_card", "track_data",
})


def _identifier(value):
    return type(value) is str and _ID.fullmatch(value) is not None


def _sandbox_session_url(value):
    if type(value) is not str or len(value) > 256:
        raise ValueError("invalid hosted checkout URL")
    if any(ord(ch) < 33 or ord(ch) > 126 for ch in value):
        raise ValueError("invalid URL characters")
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise ValueError("invalid hosted checkout URL") from exc
    if (parsed.scheme != "https" or parsed.netloc != _SANDBOX_HOST
            or parsed.username is not None or parsed.password is not None
            or parsed.port is not None or parsed.query or parsed.fragment
            or not _SESSION_PATH.fullmatch(parsed.path)):
        raise ValueError("non-allowlisted sandbox checkout URL")
    return value


def preview_hosted_checkout(*, session_url, booking_id, trusted_booking_id,
                            authenticated_actor_id, trusted_learner_id,
                            booking_evidence_verified, sandbox_enabled,
                            request_fields=None):
    """Validate a server-sourced *mock* session; no redirect or payment.

    trusted_* and authenticated_actor_id MUST come from a future authenticated
    server adapter, never from untrusted browser request fields.
    """
    if type(request_fields) is not dict or request_fields:
        # The only permitted public payload is empty: reject card data and
        # every unexpected key, including future card aliases.
        if type(request_fields) is not dict or (
                any(str(key).lower() in _FORBIDDEN_FIELDS
                    for key in request_fields)):
            raise ValueError("card data and untrusted fields prohibited")
        raise ValueError("untrusted checkout request fields prohibited")
    if not all(_identifier(v) for v in (
            booking_id, trusted_booking_id,
            authenticated_actor_id, trusted_learner_id)):
        raise ValueError("invalid booking or participant identity")
    if not hmac.compare_digest(booking_id, trusted_booking_id):
        raise PermissionError("booking mismatch")
    if not hmac.compare_digest(authenticated_actor_id, trusted_learner_id):
        raise PermissionError("not booking learner")
    if booking_evidence_verified is not True or type(booking_evidence_verified) is not bool:
        raise PermissionError("booking evidence not verified")
    if sandbox_enabled is not True or type(sandbox_enabled) is not bool:
        raise PermissionError("sandbox-only gate")
    safe_url = _sandbox_session_url(session_url)
    return {
        "booking_id": booking_id,
        "hosted_checkout_url": safe_url,
        "provider_host": _SANDBOX_HOST,
        "status": "SANDBOX_REVIEW_ONLY",
        "card_data_collected": False,
        "card_data_stored": False,
        "redirect_enabled": False,
        "real_payment_enabled": False,
        "real_payout_enabled": False,
        "operating_db_connected": False,
    }


def render_checkout_review_html(preview):
    """Static read-only review; NEVER put the session URL/token in HTML."""
    if type(preview) is not dict or preview.get("status") != "SANDBOX_REVIEW_ONLY":
        raise ValueError("review-only preview required")
    for field in ("card_data_collected", "card_data_stored", "redirect_enabled",
                  "real_payment_enabled", "real_payout_enabled",
                  "operating_db_connected"):
        if preview.get(field) is not False:
            raise ValueError("unsafe checkout state")
    if preview.get("provider_host") != _SANDBOX_HOST:
        raise ValueError("invalid sandbox host")
    booking = preview.get("booking_id")
    if not _identifier(booking):
        raise ValueError("invalid booking identifier")
    # Re-validate URL but do not render it, even as an HTML attribute.
    _sandbox_session_url(preview.get("hosted_checkout_url"))
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" '
        'content="default-src &#39;none&#39;; base-uri &#39;none&#39;; '
        'form-action &#39;none&#39;">'
        '<title>격리 결제 화면 검토</title></head><body><main>'
        '<h1>제공업체 호스팅 결제 화면: 안전성 검토</h1>'
        '<p role="status">모의 환경 전용 · 카드 입력 없음 · 이동 및 결제 불가</p>'
        '<p>예약: ' + html.escape(booking, quote=True) + '</p>'
        '<p>테스트 호스트: ' + _SANDBOX_HOST + '</p>'
        '<p>실제 제공업체 연동·독립 QA·승인 전 사용 금지</p>'
        '</main></body></html>'
    )
