# Team13 ↔ Team14 D2 서버 상품 계약 — 검증 관문

기준일 2026-10-29 · 14번 독립 브랜치: `team14/business-systems-audit-20261028` · 실제 배포 미검증

## 1. 계약 필드
서버가 예약 생성과 같은 영속 DB 트랜잭션에서 `booking_product_snapshots`를 기록해야 한다.

| 필드 | 조건 |
|---|---|
| booking_id | 원본 `bookings.id`, PRIMARY KEY |
| product_code | `trial_15` / `partner_25` / `professional_25` |
| duration_minutes | 정확히 15/25/25 |
| price_krw | 정확히 6,000/10,000/15,000 KRW |
| currency | KRW |

서버 생성 이벤트에서 `bookingId`, `amount`, `eventId`, `learnerId`, `teacherId`와 해당 스냅샷을 연결해야 한다. 클라이언트의 `price_krw`, `users.price` 기본값이나 테스트의 수동 SQL 업데이트를 금전 원장 기준으로 삼지 않는다. 가격을 바꿔야 하면 **새 예약/명시적 정책 변환**으로 처리한다. 기존 예약 금액의 사후 수정 불가.

## 2. 단일 신뢰 흐름과 14번 현행 구현
1. 13번: 예약 생성 시 인증된 서버 정책으로 상품 선택; 13번 담당 코드에 원자적으로 스냅샷 생성.
2. 14번: `verify_server_product_contract(server_db, booking_id, trusted_event)`는 스냅샷/예약 금액/완료 이벤트 금액 일치 검사. 테이블 또는 행이 없으면 `CONTRACT_MISSING`으로 **정산 매핑 거부**.
3. 14번: `bind_server_booking_product`는 서버가 만든 스냅샷과 제품코드·강사 권한이 같은 경우에만 75% 강사, 25% 플랫폼 측(소개 보상 포함) 모의 원장을 생성한다.
4. 13번: `verified_event_for_team14`의 서버 검증 완료 이벤트만 14번 `settle_verified_instant_event`에 전달해야 한다.
5. 취소/전액·부분 환불은 같은 booking ID와 원래 요율 스냅샷을 참조하여 원장 역분개. 중복 eventId/refundId는 추가 지급 0. 영속 DB 재시작에서도 동일.

## 3. 정확한 테스트 범위와 남은 차단
- 14번 독립 HTTP 테스트는 **서버 스냅샷을 가상 테이블로 모델링하여** (실제 13번 구현 아님) 학습자·강사 매칭→완료 이벤트→75:25 모의정산→부분환불→재시작을 검증했다. 이때 테스트 초기 파트너 `users.price`를 변경하는 코드는 여전히 **13번 실제 상품선택 구현 전 임시 픽스처**다. 이는 공동 완료 증거가 아니다.
- 13번 현재 브랜치 `phase3/instant_matching.py`는 예약 금액에 `partner['price']` 사용, `booking_product_snapshots` 생성 및 이벤트에 상품코드 전달 경로가 **미구현**으로 확인됨.
- 따라서 **13↔14 실제 서버 상품 교차 검증 실패/미완료**, 독립 14번 테스트 CI 통과와 분리. 99 Render 실제 배포/로그인/관리자/E2E는 미검증.
- 11번·13번이 예약 생성 DB 스냅샷과 역할/가격 계약을 구현한 후, 14번은 테스트 SQL 삽입과 `users.price` 변경 픽스처를 **전부 제거**, 3상품 각각 신규 예약/취소/완료/환불/중복/재시작 E2E를 검증해야 공동 승인 가능.

## 4. 비지급 경계
본 계약은 테스트 모의 원장 전용이며 실제 PG·송금·환불 API 호출은 금지. `real_money=False`, `payment_executed=False`, `payout_eligible=False` 유지. 기존 `main`·실서비스 DB 변경 금지.
