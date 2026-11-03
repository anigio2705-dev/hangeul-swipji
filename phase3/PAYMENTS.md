# PG 테스트 연결 경계 — 2026-10-27

## 현재 가능한 것과 확인하지 못한 것

`payments.py`는 Stripe Checkout **테스트 전용** 서버 어댑터다. 실제 공식 API 주소로 요청을 만들 수 있지만, 이번 작업에서는 Stripe 테스트 계정·키·webhook 등록·제공자 결제 화면을 사용하지 않았다. 로컬 전송 모형을 사용한 **계약 검사 9개 통과**는 실제 PG sandbox 통과가 아니다. 한국 사업자의 Stripe 가입·서비스 제공 가능성, 마켓플레이스 중개 및 강사 지급 심사는 별도 확인이 필요하다. Stripe를 최종 PG로 확정한 것도 아니다.

기존 `pay-test`는 외부 PG와 무관한 모의 원장이다. 이를 Stripe 테스트 결제나 실제 승인으로 표시하면 안 된다. 제공자 테스트 거래 역시 현금 결제가 아니다. 라이브 키·라이브 이벤트·실제 지급을 허용하는 옵션은 구현하지 않았다.

## 모듈 API

```python
checkout = payments.create_checkout(
    booking,                     # DB에서 읽은 불변 id + price(KRW 정수)
    success_url=server_url,       # 서버 설정값; 요청 본문에서 받지 않음
    cancel_url=server_url,
)
# id, url, amount, currency='krw', provider='stripe', mode='provider-test'

event = payments.verify_event(raw_body, stripe_signature, webhook_secret)
confirmed = payments.validate_checkout_event(event, booking, stored_checkout_id)
# event_id, booking_id, session_id, amount, currency, provider, mode
```

- 서버 환경변수 `HS_STRIPE_TEST_SECRET_KEY`가 없으면 `NotConfigured`로 종료하고 네트워크 요청을 하지 않는다. `sk_test_`만 허용하며 `sk_live_`, `rk_live_` 및 기타 키는 거부한다. 키는 응답·로그·HTML·GitHub에 넣지 않는다.
- POST 대상은 `https://api.stripe.com/v1/checkout/sessions`로 고정한다. 결제 API의 리디렉션은 따르지 않는다. 사용자 이메일·성명·강사 정보 대신 불투명 예약 ID만 metadata에 전송한다.
- KRW 금액은 원 단위 정수이며 100배로 바꾸지 않는다. 카드 정보를 서버에서 수집하지 않고 Stripe가 호스팅하는 Checkout만 요청한다.
- 예약 ID에서 결정적으로 만든 Idempotency-Key로 재요청한다. 서버는 **예약당 하나의 저장된 session**을 관리하고 예약 금액·통화·자료 스냅샷을 바꾸지 않아야 한다.
- Checkout 응답의 테스트 모드·정수 금액·통화·예약 metadata·반환 URL 호스트를 검증한다. 결제 성공 반환 URL은 편의 이동용이며 예약 상태를 결제됨으로 변경하는 근거가 아니다.
- raw body의 정확한 바이트에 대해 HMAC-SHA256을 확인한 뒤 JSON을 해석한다. 서명 timestamp는 과거/미래 모두 최대 300초로 제한한다. 키 교체용 복수 v1 서명은 허용하지만 중복 timestamp는 거부한다.
- `checkout.session.completed`와 `payment_status=paid`, `status=complete`, 양쪽 `livemode=false`, 저장된 테스트 session ID, 예약 ID, metadata, KRW 금액이 모두 일치해야 한다. Connect 계정 이벤트·지원하지 않는 이벤트·비동기 미결제·라이브 이벤트는 결제 성공으로 처리하지 않는다.

## 서버 통합의 필수 불변 조건

모듈은 DB를 수정하지 않는다. 호출 서버가 아래 작업을 **하나의 원자적 트랜잭션**에서 수행해야 한다.

1. 원시 webhook 서명 확인 후 이벤트 종류를 판별한다. 등록된 테스트 webhook 서명 비밀은 서버에서만 읽는다. 라이브와 테스트 webhook 비밀을 혼용하지 않는다.
2. 저장된 provider/session으로 예약을 찾는다. 요청 metadata만 믿어 임의 예약을 결제 처리하지 않는다. 원래 예약자·금액·통화·예약 상태를 재검증한다.
3. `(provider,event_id)`를 UNIQUE로 저장하고, session당 청구도 유일하게 만든다. 동일 이벤트 재전송 또는 다른 event ID로 같은 session이 다시 배달되어도 원장은 한 번만 반영한다. 중복 전송은 안전하게 확인 응답하며 금액을 추가하지 않는다.
4. 취소·환불·이미 다른 방법으로 결제된 예약에는 무조건 성공을 덮어쓰지 않는다. 비정상 상태는 운영 검토 대상으로 기록한다.
5. 실제 확인된 **provider-test** 거래와 로컬 **simulated-test-only** 청구를 분리해 표시한다. 실제 현금 결제는 어느 쪽에도 발생하지 않는다.
6. 원장·이벤트·상태 변경을 함께 커밋한다. 재처리 실패 시 모두 롤백하고 재전송으로 복구할 수 있어야 한다. 비밀키·원시 카드 정보·서명 비밀은 감사 로그에 남기지 않는다.

환불·차지백·정산·강사 지급을 제공자 API로 실행하는 어댑터는 아직 없다. 현재 환불은 로컬 모의 역분개이며 실제 제공자 환불로 표시하지 않는다. 완료된 수업의 가상 정산도 실제 현금 지급이 아니다.

## 외부 PG sandbox 확인에 남은 것

테스트 계정/사업자 이용 가능성·가맹점 승인 → 테스트 키와 별도 webhook 비밀을 안전한 서버 환경에 설정 → 계정 API 버전 기록 및 호환 검사 → 승인된 테스트 URL/터널에서 서명 webhook 수신 → Stripe 테스트용 결제수단으로 성공·거절·3DS·취소를 실행 → 실제 제공자 이벤트/금액/중복 배달을 대사 → 제공자 환불/차지백 흐름 추가·검사. 이 단계들은 자격증명과 제공자 확인 없이 완료했다고 보고하지 않는다.

운영 전에는 결제사업자와 한국 사업자/마켓플레이스/KYC/해외 수취/세무/개인정보 이전을 확인하고, 변호사·세무사·보안 검토를 거쳐야 한다. 이 어댑터는 그 승인을 대체하지 않는다.

## 공식 문서 확인

조회 2026-10-27 KST. 교육 자료·키·결제 정보는 복제하거나 공개하지 않았다.

- [Checkout Session 생성](https://docs.stripe.com/api/checkout/sessions/create): 서버 요청, amount_total, currency, livemode, metadata 및 Checkout URL.
- [Webhook 서명·재전송 관리](https://docs.stripe.com/events/manage-webhook-endpoints): raw body·서명·timestamp 및 중복 이벤트 처리.
- [테스트 환경](https://docs.stripe.com/testing): sandbox 거래는 자금을 이동하지 않으며 테스트 API 키/테스트 결제수단을 사용한다.
- [지원 통화](https://docs.stripe.com/currencies): KRW의 zero-decimal 금액 표현. 사업자 국가별 지원과 계정 이용 가능성은 별도 확인한다.

## 이번 서버 연결 결과

`POST /api/bookings/{id}/checkout-test`에서 서버 예약 금액으로 세션을 만들고, `POST /api/payments/stripe-test/webhook`에서 raw 서명·세션·금액·통화·예약·모드를 재검증한다. 원장과 이벤트·상태는 하나의 DB 트랜잭션으로 처리하며 동일/다른 이벤트 ID로 같은 세션을 재전송해도 모의 청구는 한 번이다. 이미 PG 세션이 있으면 로컬 `pay-test`와 혼합하지 않는다. 성공 반환 URL은 상태를 바꾸지 않는다. 만료·취소된 예약으로 늦게 도착한 이벤트는 보류·감사 기록을 남기고 수업을 다시 열지 않는다.

HTTP 계약 검사는 외부 네트워크 전송을 모형으로 대체한다. 실제 PG sandbox 계정/API 화면/카드/웹훅 등록은 이번에도 **미실행**이다. 현재 localhost Host 제한 때문에 외부 PG의 실 웹훅을 직접 받을 공개 endpoint도 배포하지 않았다. 승인된 별도 테스트 호스트·TLS·비밀 관리와 테스트 계정이 필요하다. 한국 사업자의 Stripe 이용 가능성 및 최종 PG 선정은 검토 전이다. 모듈이 있다는 사실을 PG 심사·실 sandbox 검증 통과로 보고하지 않는다.
