"""Stripe TEST-only boundary. No live key, cash payout, or payment success shortcut.

The caller owns persistent transaction/idempotency storage. This module never changes
booking state. Contract tests with a fake transport do not prove provider integration.
"""
import hashlib
import hmac
import json
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

ENDPOINT = 'https://api.stripe.com/v1/checkout/sessions'
MAX_EVENT_BYTES = 65536


class PaymentError(Exception):
    pass


class NotConfigured(PaymentError):
    pass


def test_key(value=None):
    key = value if value is not None else os.environ.get('HS_STRIPE_TEST_SECRET_KEY', '')
    if not key:
        raise NotConfigured('Stripe 테스트 자격증명이 설정되지 않았습니다. 실제 PG 검증은 미완료입니다.')
    if not isinstance(key, str) or not re.fullmatch(r'sk_test_[A-Za-z0-9_]{8,}', key):
        raise PaymentError('테스트 전용 sk_test_ 키만 허용합니다. 실결제 키는 사용할 수 없습니다.')
    return key


def configured():
    try:
        test_key()
        return True
    except PaymentError:
        return False


def _booking(booking):
    try:
        bid, amount = booking['id'], booking['price']
    except (KeyError, TypeError):
        raise PaymentError('서버의 불변 예약 스냅샷이 필요합니다.') from None
    if not isinstance(bid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', bid):
        raise PaymentError('잘못된 예약 ID입니다.')
    if isinstance(amount, bool) or not isinstance(amount, int) or not 1000 <= amount <= 1000000:
        raise PaymentError('예약 금액은 1,000~1,000,000원 정수여야 합니다.')
    return bid, amount


def _return_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise PaymentError('서버가 정한 반환 URL이 필요합니다.')
    u = urlsplit(value)
    if u.username or u.password or not u.hostname or u.fragment:
        raise PaymentError('잘못된 반환 URL입니다.')
    if not (u.scheme == 'https' or (u.scheme == 'http' and u.hostname in ('127.0.0.1', 'localhost'))):
        raise PaymentError('HTTPS 또는 로컬 테스트 반환 URL만 허용합니다.')
    return value


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PaymentError('결제 API 리디렉션을 거부했습니다.')


def _transport(request, timeout=15):
    # Do not expose request headers, secret keys, or raw provider errors in logs/responses.
    try:
        with build_opener(_NoRedirect).open(request, timeout=timeout) as response:
            return response.read(MAX_EVENT_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError):
        raise PaymentError('Stripe 테스트 API 요청에 실패했습니다. 서버의 설정과 제공자 상태를 확인하세요.') from None


def _json(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_EVENT_BYTES:
        raise PaymentError('잘못되거나 너무 큰 결제 응답입니다.')
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise PaymentError('결제 응답 JSON을 확인하세요.') from None
    if not isinstance(value, dict):
        raise PaymentError('결제 응답 객체가 필요합니다.')
    return value


def create_checkout(booking, *, success_url, cancel_url, api_key=None, transport=None):
    """Create a provider test Checkout Session for one immutable KRW booking.

    `booking` must come from the server DB, never client-supplied price/metadata.
    Injected `transport(Request, timeout=15) -> bytes` is for contract tests only.
    """
    key = test_key(api_key)
    bid, amount = _booking(booking)
    params = {
        'mode': 'payment',
        'payment_method_types[0]': 'card',
        'line_items[0][price_data][currency]': 'krw',
        'line_items[0][price_data][unit_amount]': str(amount),
        'line_items[0][price_data][product_data][name]': 'Hangeul Swipji TEST lesson',
        'line_items[0][quantity]': '1',
        'client_reference_id': bid,
        'metadata[booking_id]': bid,
        'metadata[hs_mode]': 'phase3-test-only',
        'success_url': _return_url(success_url),
        'cancel_url': _return_url(cancel_url),
    }
    # A network retry for the same booking uses exactly the same provider request key.
    # The caller must persist one session per booking and reject changed booking snapshots.
    idempotency = 'hs3-test-' + hashlib.sha256(bid.encode()).hexdigest()
    request = Request(ENDPOINT, data=urlencode(params).encode(), method='POST', headers={
        'Authorization': 'Bearer ' + key,
        'Content-Type': 'application/x-www-form-urlencoded',
        'Idempotency-Key': idempotency,
    })
    session = _json((transport or _transport)(request, timeout=15))
    sid = session.get('id')
    if not isinstance(sid, str) or not sid.startswith('cs_test_') or session.get('livemode') is not False:
        raise PaymentError('실결제 또는 알 수 없는 Checkout 응답을 거부했습니다.')
    if session.get('mode') != 'payment' or session.get('currency') != 'krw' or not isinstance(session.get('amount_total'), int) or isinstance(session.get('amount_total'), bool) or session.get('amount_total') != amount:
        raise PaymentError('Checkout 금액·통화·유형이 예약과 일치하지 않습니다.')
    meta = session.get('metadata')
    if not isinstance(meta, dict) or session.get('client_reference_id') != bid or meta.get('booking_id') != bid or meta.get('hs_mode') != 'phase3-test-only':
        raise PaymentError('Checkout 예약 연결이 일치하지 않습니다.')
    url = session.get('url')
    if not isinstance(url, str):
        raise PaymentError('Checkout 주소가 없습니다.')
    dest = urlsplit(url)
    if dest.scheme != 'https' or dest.hostname != 'checkout.stripe.com' or dest.username or dest.password or dest.port not in (None, 443):
        raise PaymentError('허용되지 않은 Checkout 주소입니다.')
    return {'id': sid, 'url': url, 'amount': amount, 'currency': 'krw', 'provider': 'stripe', 'mode': 'provider-test'}


def verify_event(raw, signature, secret, now=None, tolerance=300):
    """Verify the EXACT raw bytes before parsing JSON; reject stale/future/live events.

    A valid signature alone does not make an event authorized for a booking.
    Call validate_checkout_event, then persist event/session IDs atomically with ledger.
    """
    if not isinstance(secret, str) or not secret.startswith('whsec_') or len(secret) < 14:
        raise NotConfigured('테스트 webhook 서명 비밀이 설정되지 않았습니다.')
    if not isinstance(raw, bytes) or len(raw) > MAX_EVENT_BYTES or not isinstance(signature, str) or len(signature) > 4096:
        raise PaymentError('잘못된 webhook 요청입니다.')
    if isinstance(tolerance, bool) or not isinstance(tolerance, int) or not 1 <= tolerance <= 300:
        raise PaymentError('Webhook 허용 시간은 1~300초입니다.')
    parts = {}
    for pair in signature.split(','):
        key, sep, value = pair.strip().partition('=')
        if sep:
            parts.setdefault(key, []).append(value)
    ts = parts.get('t', [])
    if len(ts) != 1 or not ts[0].isdigit() or len(ts[0]) > 12:
        raise PaymentError('Webhook 서명 시각이 잘못되었습니다.')
    timestamp = int(ts[0])
    current = time.time() if now is None else now
    if abs(current - timestamp) > tolerance:
        raise PaymentError('Webhook 서명의 유효 시간이 지났거나 미래 시각입니다.')
    expected = hmac.new(secret.encode(), str(timestamp).encode() + b'.' + raw, hashlib.sha256).hexdigest()
    signatures = parts.get('v1', [])
    if not any(re.fullmatch(r'[0-9a-f]{64}', v) and hmac.compare_digest(expected, v) for v in signatures):
        raise PaymentError('Webhook 서명이 일치하지 않습니다.')
    event = _json(raw)
    if event.get('livemode') is not False or not isinstance(event.get('id'), str) or not re.fullmatch(r'evt_[A-Za-z0-9_]{1,120}', event['id']):
        raise PaymentError('테스트 전용 이벤트만 처리합니다.')
    return event


def validate_checkout_event(event, booking, session_id):
    """Authorize a signed successful test payment against a previously stored session.

    Other event kinds must not mark a booking paid. Refunds require a separate,
    provider-aware flow; this module intentionally does not pretend to handle them.
    """
    bid, amount = _booking(booking)
    if not isinstance(event, dict) or event.get('livemode') is not False or event.get('type') != 'checkout.session.completed':
        raise PaymentError('지원하지 않는 결제 이벤트입니다.')
    if not isinstance(event.get('id'), str) or not re.fullmatch(r'evt_[A-Za-z0-9_]{1,120}', event['id']) or event.get('account'):
        raise PaymentError('연결 계정 또는 잘못된 이벤트 ID입니다.')
    data = event.get('data')
    obj = data.get('object') if isinstance(data, dict) else None
    if not isinstance(obj, dict) or obj.get('object') != 'checkout.session':
        raise PaymentError('Checkout 이벤트 객체가 필요합니다.')
    if not isinstance(session_id, str) or not session_id.startswith('cs_test_') or obj.get('id') != session_id or obj.get('livemode') is not False:
        raise PaymentError('저장된 테스트 Checkout과 일치하지 않습니다.')
    if obj.get('mode') != 'payment' or obj.get('payment_status') != 'paid' or obj.get('status') != 'complete':
        raise PaymentError('제공자가 확인한 완료 결제가 아닙니다.')
    if not isinstance(obj.get('amount_total'), int) or isinstance(obj.get('amount_total'), bool) or obj.get('amount_total') != amount or obj.get('currency') != 'krw':
        raise PaymentError('결제 금액 또는 통화가 예약과 다릅니다.')
    meta = obj.get('metadata')
    if not isinstance(meta, dict) or meta.get('booking_id') != bid or meta.get('hs_mode') != 'phase3-test-only' or obj.get('client_reference_id') != bid:
        raise PaymentError('다른 예약 또는 실행 모드의 이벤트입니다.')
    return {'event_id': event['id'], 'booking_id': bid, 'session_id': session_id, 'amount': amount, 'currency': 'krw', 'provider': 'stripe', 'mode': 'provider-test'}
