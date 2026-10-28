# Team14 5차: 영속 모의 월 과정 거래 / 예약 이벤트

## 변경
- 기존 14개 테스트 및 `team14_monthly_sim.py` 보존.
- `phase3/team14_persistent.py`: SQLite 별도 모의 저장소. 월 과정 ID, 회차 ID, 예약 ID, 거래 ID, operation ID, KRW 전용 통화, 원 단위 정수, 10^15 상한.
- `phase3/test_team14_persistent.py`: 8개 신규 테스트.
- `.github/workflows/team14-monthly-tests.yml`: 기존 14개 + 신규 8개 checkout CI 실행.
- 다른 팀 코드, 공통 DB/서버, 운영 결제·송금·환불 API 미수정.

## 계약 및 안전성
- Team11 ID 정규식/오류 코드 VALIDATION_ERROR, NOT_FOUND, CONFLICT, INVALID_STATE와 형태 호환. 실제 공통 모듈을 import하지 않으므로 계약 승인은 별도.
- Team13 예약 이벤트는 booking_id와 booking_state를 입력받는 **모의 인터페이스**. 실제 예약 테이블에 연결하지 않음. 완료=completed, 취소=cancelled, 환불=refunded 입력만 허용. 예약 상태 원천 검증/이벤트 서명은 미구현.
- BEGIN IMMEDIATE 및 SQLite UNIQUE(transaction_id,kind), operation_id+payload 재전송 저장, 실패시 rollback. SQLite 파일 재개방 이후에도 기록 유지. 다중 서버/네트워크 중복 전송·외부 결제 멱등성은 별도 미검증.
- 가상 보수=80%, 소개 가상 보상=3%, 플랫폼 가상 잔액=17%. **미승인 테스트 가정**, 실제 지급·다단계 보상 없음.
- 완료된 회차 환불 금지; 사후 분쟁/차지백 역분개는 정책 승인 후 별도 설계.
- 취소는 미완료·미환불 회차만 허용하고 해당 회차 전체 금액의 음수 역분개를 남김.

## 테스트 증거
- 로컬 임시 파일 `/mnt/data/team14_run/team14_persistent.py`, `test_team14_persistent.py`에서 8개 테스트 실행: **8 passed**, 0.085s. GitHub 커밋본은 동일 목적의 구현이나 파일 구성이 별도 작성되어 **GitHub SHA checkout의 테스트 통과는 아직 검증되지 않음**.
- 사용자 총괄본부: 기존 14개 통과 보고. 이번 작업에서는 14개 재실행하지 않았음.
- GitHub Actions: workflow 저장 완료. **실행 URL/결과 확인 불가**. 검증 URL: https://github.com/anigio2705-dev/hangeul-swipji/actions/workflows/team14-monthly-tests.yml
- 체크아웃 SHA와 로그가 확보될 때까지 CI PASS 또는 통합 승인으로 판정하지 않음.

## 정산 기대 검증표
| 사례 | 계약 | 강사 | 소개 | 플랫폼 | 환불 | 미처리 | 총합 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 4회×20,000, 2회 완료·1회 부분+잔여 환불·1회 취소 | 80,000 | 32,000 | 1,200 | 6,800 | 40,000 | 0 | 80,000 |

## 미확정
월 과정 가격 할인, 취소 수수료, 환불 시점·귀책, 부분 완료 후 분쟁, 정산 지급 주기, 실 PG 비용·세금, 예약 이벤트 인증, 실 운영 DB 마이그레이션, 다중 프로세스/DB 영속성, 다통화 지원. 사업 정책·실제 금전 거래는 사장 승인 전 보류. 통합·배포 금지.
