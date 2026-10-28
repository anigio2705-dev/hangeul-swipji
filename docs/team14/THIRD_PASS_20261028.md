# Team14 3차 검증 및 공통 계약 대조 (2026-10-28)

## 검증 대상
- 실제 GitHub blob 확인: `phase3/team14_monthly_sim.py` (52236930e09fcb0801dc3d9ac75ce229b3e34187), `phase3/test_team14_monthly_sim.py` (8cf922e62734df382157710866f7a7607b2219ac).
- 기존 6개 테스트 + 새 `phase3/test_team14_monthly_boundaries.py` 8개 = 14개.
- CI `.github/workflows/team14-monthly-tests.yml`: push / workflow_dispatch, actions/checkout@v4, `git rev-parse HEAD`, `python -m unittest discover -s phase3 -p 'test_team14_monthly*.py' -v`.
- 로컬 git clone 시도: `git clone --branch team14/business-systems-audit-20261028 --depth 1 https://github.com/anigio2705-dev/hangeul-swipji.git ...` => exit 128, `Could not resolve host: github.com`.
- CI run 조회는 GitHub connector fetch URL 허용 제한으로 실패. **실제 실행 로그와 PASS 결과 확보하지 못함.**
- 검증 상태: TESTS WRITTEN / EXECUTION UNVERIFIED. CI 로그 확보 전 병합 불가.

## 경계 테스트
1. 0원 계약 거부, 10^15 KRW 단일 회차 정산.
2. 통화 인수 USD를 기존 인터페이스에 넣으면 TypeError: 명시적 통화 검증이 아니라 통화 모델 자체 부재라는 증거.
3. 범위 밖/실수/bool 회차 번호, 완료 후 환불 거부, 환불 후 정산 거부.
4. 동일 키/동일 내용 재전송 무효, 동일 키/상이한 내용 거부.
5. 부분 환불 2500+3500의 음수 역분개와 총액 보존.
6. 실패 요청의 키 재사용.
7. 1원 단위 내림 계산 및 이중 정산 방지.
8. 서로 다른 Month 객체의 동일 키는 각각 처리: 영속적/전역 멱등성 미구현.

## 정산 검증표 (테스트 기대값, 실행 검증 아님)
| 사례 | 원금 | 강사 가상보수 | 직접소개 가상보상 | 플랫폼 가상잔액 | 환불 | 미처리 | 합계 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 4회×20,000원, 2회 완료·2회 전액 환불 | 80,000 | 32,000 | 1,200 | 6,800 | 40,000 | 0 | 80,000 |
| 3회×10,000원, 1회 완료·2회 부분/미처리 | 30,000 | 8,000 | 300 | 1,700 | 6,000 | 14,000 | 30,000 |
| 3회×1원 완료, 정수 내림 | 3 | 0 | 0 | 3 | 0 | 0 | 3 |

수수료 20%, 직접 소개 보상 3%는 **미승인 테스트 가정**. 플랫폼 가상잔액은 실제 순이익이 아니며 PG 비용/세금/환불충당금은 모델링되지 않음.

## Team11 계약 대조
Team11 `phase3/common_contract.py`와 `docs/team11/THIRD_PASS_20261028.md` 직접 조회.
- ID: Team11 `validate_id` = ASCII 영숫자/밑줄/하이픈 1~128자. Team14는 `operation_id` 비어 있지 않은 문자열만 검증, month_id/booking_id/lesson_id/transaction_id 없음. **충돌/미구현**.
- 금액: Team11 `validate_amount_minor` = 0..10^15 정수. Team14 가격은 1 이상의 정수이며 최대값 제한 없음. 0원 계약 허용 여부와 상한이 불일치. 통화 코드는 Team14에 없음. **충돌/미구현**.
- 상태: Team11 거래 `pending/authorized/captured/failed/refunded/partially_refunded`, 예약 `reserved/expired/cancelled/test_paid/in_class/completed/refunded`; Team14는 `completed` set, `refunded` dict 및 음수 ledger만 보유. 매핑/전이 계약 미정. **충돌/미구현**.
- 오류: Team11 `VALIDATION_ERROR/CONFLICT/INVALID_STATE` 등 구조화 코드 후보. Team14는 `ContractError(ValueError)`만 발생. **어댑터 필요**.
- 멱등성: Team14는 Month 인스턴스 단위만 보장; 영속 저장/거래 범위 식별자 없음. **운영 사용 불가**.
- 기존 역할/승인 규칙 및 실제 예약 ID 연결 없음. 11번 승인 전 공통 DB/서버 미수정.

## 정책 및 운영 차단
- 부분 제공 회차의 처리, 완료 후 분쟁 환불·강사 보수 역분개, 월 할인, 가격 배분, 수수료/소개율, 지급 자격, 환율·통화, 과세/PG 비용 미승인.
- 실제 결제·송금·추천 보상 지급·다단계 보상은 구현/활성화하지 않음.
- 다른 팀 코드 변경, 통합, 배포 금지.
