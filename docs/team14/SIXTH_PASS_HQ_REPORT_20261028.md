# Team14 6차 실행 보고 / 총괄본부 제출

## 코드
- 기준: 14번 5차 `ab05d827c2d5ba847bcc2dcd06922640846c126b`.
- 기존 22개 테스트와 모의 원장 보존.
- 신규 `phase3/team14_booking_events.py`: 예약/월 과정/회차/거래/이벤트 ID를 필수로 받는 독립 예약 이벤트 어댑터. 완료, 취소, 부분 환불; 원장과 연결. 요청 재전송은 영속 operation_id 및 transaction_id 제약으로 중복 방지.
- 신규 `phase3/test_team14_booking_events.py`: 8개 테스트 작성. 예약 ID 불일치, 이벤트 중복, 상태/통화 불일치, 취소, 부분 환불, 중복 재시도.
- `.github/workflows/team14-monthly-tests.yml`: 기존 14개 + 영속 원장 8개 + 예약 이벤트 8개 = **총 30개 기대**.

## 검증 상태
- GitHub 실제 소스와 11번 `common_contract.py`, 13번 `server.py` 및 팀13 문서를 조회.
- 실제 GitHub Actions 실행 로그/exit code는 확보하지 못함. **30개 테스트 통과로 보고 금지**. CI 상태 HOLD.
- Actions workflow URL: https://github.com/anigio2705-dev/hangeul-swipji/actions/workflows/team14-monthly-tests.yml
- 테스트 명령: `python -m unittest discover -s phase3 -p 'test_team14_monthly*.py' -v`; `python -m unittest discover -s phase3 -p 'test_team14_persistent.py' -v`; `python -m unittest discover -s phase3 -p 'test_team14_booking_events.py' -v`.

## 계약 대조
- Team11 ID 및 오류 코드 형태는 동일한 패턴으로 사용. 11번 공식 모듈을 import하지 않음.
- Team13 기존 `server.py` 예약 상태는 실제 `reserved`, `test_paid`, `in_class` 중심이며, 이 어댑터는 `completed/cancelled/refunded` 최종 이벤트를 요구함. **13번 이벤트 생산/인증 경로가 아직 연결되지 않았으므로 실제 종단간 연결은 HOLD**.
- 이벤트 호출자 신뢰 검증, 예약 소유권 및 강사 승인, 예약 상태 전이의 원천 인증은 13/11번과 공동 계약 확정 필요. 어댑터를 공개 HTTP 엔드포인트에 직접 노출하면 안 됨.
- Team13 즉시 자동 매칭 변경 없음. 공통 DB/server 및 타 팀 브랜치 수정 없음.

## 정산 기대 검증표 (실행 결과 아님)
| 사례 | 총액 | 강사 | 소개 | 플랫폼 | 환불 | 미처리 |
|---|---:|---:|---:|---:|---:|---:|
| 4회×20,000, 2회 완료, 1회 전액 부분환불 누적, 1회 취소 | 80,000 | 32,000 | 1,200 | 6,800 | 40,000 | 0 |

## 총괄본부 승인 요청
- 부서: 14 사업 시스템팀.
- 요청: 11/13 예약 이벤트 생성 및 인증/상태 전이 계약과 14번 모의 원장 연결의 기술 승인, 15번 QA의 실제 Actions 실행 결과 검증.
- 이유: 원천 예약 이벤트 인증·완료 전이 경로가 아직 없음.
- 위험: 임의 이벤트로 가짜 수업 완료 및 모의 정산, 운영 연결 시 금전 피해.
- 미승인 영향: 실제 통합/배포 HOLD, 독립 모의 테스트 지속.
- 권장안: 11·13번의 인증된 내부 이벤트 계약 확정 후 15번 교차 검증, 총괄본부 승인 전까지 독립 어댑터만 유지.
- 사업 정책: 20% 수수료, 3% 소개 보상은 미승인 테스트 가정. 실제 결제/송금/환불/보상 지급 전부 비활성. 사장 승인 전 HOLD.
