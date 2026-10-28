# 13↔14 제3호 D2 서버 확정 모의 상품 계약 v1

**상태**: 팀13 코드 변경 및 CI 증거는 별도로 확인. 실제 99 Render 배포와 14번 교차 검증은 독립된 필수 관문. 운영 결제/정산 금지.

## 상품 (14번 `phase3/team14_initial_products.py`의 `TEST_CATALOG` 규격과 동일)
| product_code | duration_minutes | price_krw | currency | instant 기본 적용 |
|---|---:|---:|---|---|
| `trial_15` | 15 | 6000 | KRW | 유효한 서버 상품이지만 별도 선택 UI는 미연결 |
| `partner_25` | 25 | 10000 | KRW | 승인된 일반 파트너 자동매칭 |
| `professional_25` | 25 | 15000 | KRW | 승인된 전문 강사 자동매칭 |

## 계약 및 데이터 흐름
1. `phase3/instant_matching.py`의 `server_product_for_partner()`가 서버 DB의 승인된 역할로 기본 상품을 선택한다. 기존 `users.price=20000`은 즉시매칭 가격을 결정하지 않는다. 브라우저 금액도 사용하지 않는다. trial_15 선택은 차후 명시적 서버 검증 정책/버튼 필요.
2. 양측 `ready` 성공 시 동일 SQLite 트랜잭션에서 `bookings.price`와 `booking_product_snapshots(booking_id PRIMARY KEY, product_code, duration_minutes, price_krw, currency)`를 기록한다. `slots` 종료시간은 실제 상품 시간 25분을 사용한다.
3. 중복 수락은 `instant_booking_links`를 조회하고 중복 예약·상품 재생성을 방지한다. 기존 정규 예약 경로는 변경하지 않는다.
4. `lesson.completed` 및 `booking.cancelled` 이벤트의 payload에 `productCode,durationMinutes,priceKrw,currency`를 추가한다. 기존 `eventId,bookingId,amount`를 보존한다.
5. `verified_booking_product()`와 `verified_event_for_team14()`는 서버 DB 예약 금액·상품 스냅샷·14번 가격표/역할과 일치하는지 재확인하고 불일치를 409 거부한다. `verified_outbox_envelope()`에도 상품 정보를 동일하게 전달한다.
6. 팀14가 이미 구현한 `verify_server_product_contract(server_db,booking_id,trusted_event)`에 같은 테이블·필드로 연결해야 한다. 정산 금액·75/25 분배·실제 모의 환불은 **14번 원장**에서만 확정한다. 팀13은 실제 지불·PG 호출·원장 수정 없음.
7. **마이그레이션 한계**: 이전 코드에서 생성한 즉시매칭 예약에는 snapshot이 없으며, 자동으로 20,000원 레거시 값을 새 제품으로 가정하지 않고 fail closed 처리한다. 팀11·14·15가 기존 테스트 DB 보존·격리·이전 방안을 결정해야 함.
8. Jitsi 실통화/출석 증빙은 별도 문제: HTTP session-observe는 실제 미디어를 증명하지 않음. 실제 돈 이동, 운영 데이터 및 main 변경 금지.

## 14번 교차 검증 요청
- 정상 3상품: 직접 snapshot 기반 계약 검사. 즉시 자동매칭 기본 제품 2종은 역할로 선택, `trial_15`는 단독 서버 계약으로 확인하되 선택 UI는 미완료 명시.
- 예약/완료/취소/환불/재전달/재시작 뒤 `bookings.price == snapshot.price_krw == trusted_event.amount == settlement_store.lesson.amount` 검증.
- `users.price`가 20,000원이어도 25분 파트너 10,000원, 전문강사 15,000원.
- 클라이언트 가격 조작, 기존 예약 가격 조작, snapshot 변경, 재시작 유실은 정산 금지.
- 14번 `bind_server_booking_product()`와 `verify_server_product_contract()`가 역할을 포함해 일관되는지 교차 테스트, `team14_recovery` PYTHONPATH는 15번 통합 CI 담당.

## 검증 구분
- 팀13 Python/모의 브라우저 Actions: 결과 확인 뒤 정확한 SHA·job PASS 제출.
- 팀14 교차 통합 CI 및 99 Render 브라우저/DB/2기기 실통화: **독립 검증 전 미완료**.
