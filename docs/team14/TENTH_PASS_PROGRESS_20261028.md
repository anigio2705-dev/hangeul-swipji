# Team14 10차 개발 수행률·연결 계약 보고 (2026-10-28)

**원본 160개 실행표의 101~130번 30개만 평가.** 수행률은 구현 증거 기반의 **잠정 추정치**이며, 총괄본부·15번 독립 검증으로 조정 가능하다. 100%는 하나도 주장하지 않는다. 문서/테스트 코드만으로 90% 부여하지 않았다.

- 담당 30개 단순 평균: **25.7%** (합계 770 / 30).
- 이전 차수: 항목별 수행률 수치가 없어 **증가분 비교 불가**.
- 기존 44개 + 신규 8개 = **52개 테스트 코드 기대**. 총괄본부가 9차 자동 검사 성공을 보고했으나 **10차 변경 SHA의 실행 결과는 아직 미확인**.
- 10차 변경: `phase3/team14_verified_bridge.py` 및 `phase3/test_team14_verified_bridge.py`(8개). Team13 내부에서 인증된 이벤트/서버 조회가 제공되지 않으면 **fail closed**. 운영 연결은 미완료.
- 공통 데이터: Team11 ID 패턴, Team13 예약·수업 상태 후보를 따르되 Team11·13의 최신 실구현 계약이 이 브랜치에 통합되지 않았으므로 완료 판정 금지.

| 번호 | 수행률 | 구현된 내용 | 미구현·차단 사항 | 코드·검사 근거 | 다음 작업 | 팀 연결 |
|---:|---:|---|---|---|---|---|
| 101 | 30% | 소개 관계 시나리오 일부 | 역할별 실제 관계 저장 | team14_referral_scenarios.py; CI 10차 미확인 | 역할별 실제 관계 저장 | 정책·관계 DB |
| 102 | 30% | 1·2단계 후보 계산 | 승인된 단계·기간 정책 | team14_referral_scenarios.py; CI 10차 미확인 | 승인된 단계·기간 정책 | 법률/사장 |
| 103 | 50% | 모의 수익 분할 계산 | 원장 계산식 일치·세금 | team14_referral_scenarios.py; CI 10차 미확인 | 원장 계산식 일치·세금 | 11·13 |
| 104 | 30% | 완료 이벤트 모의 원장 | 확정/지급 시점 정책 | team14_referral_scenarios.py; CI 10차 미확인 | 확정/지급 시점 정책 | 13 |
| 105 | 0% | 없음 | 재수강·갱신 관계 유지 | team14_referral_scenarios.py; CI 10차 미확인 | 재수강·갱신 관계 유지 | 13 |
| 106 | 20% | 미승인 보상 후보 | 할인/포인트 중복 정책 | team14_referral_scenarios.py; CI 10차 미확인 | 할인/포인트 중복 정책 | 사장 |
| 107 | 10% | 지급 차단·법률 위험 표기 | 국가별 전문 검토 | team14_referral_scenarios.py; CI 10차 미확인 | 국가별 전문 검토 | 외부 |
| 108 | 10% | ID 계약·관계 입력 검증 | 추천 코드/링크 영속화 | team14_referral_scenarios.py; CI 10차 미확인 | 추천 코드/링크 영속화 | 11 |
| 109 | 50% | 자기/순환/중복 관계 거부 코드 | 실제 계정 악용 탐지 | team14_referral_scenarios.py; CI 10차 미확인 | 실제 계정 악용 탐지 | 11 |
| 110 | 30% | 보상 시뮬레이터 | 정책 버전 저장/표시 | team14_referral_scenarios.py; CI 10차 미확인 | 정책 버전 저장/표시 | 사장 |
| 111 | 40% | 회차 취소/환불 상태 | 노쇼·지각·귀책 표 | team14_persistent.py; CI 10차 미확인 | 노쇼·지각·귀책 표 | 13 |
| 112 | 0% | 없음 | 증거·분쟁 접수 | team14_persistent.py; CI 10차 미확인 | 증거·분쟁 접수 | 13 |
| 113 | 60% | 회차별 부분·전액 환불 계산 | 할인·귀책·실결제 연계 | team14_persistent.py; CI 10차 미확인 | 할인·귀책·실결제 연계 | 13 |
| 114 | 70% | SQLite 강사/소개/플랫폼 분리 원장 | 실 이벤트·대사·CI | team14_persistent.py; CI 10차 미확인 | 실 이벤트·대사·CI | 13·15 |
| 115 | 50% | 환불 음수 원장·중복 방지 | 완료 수업 환불의 3종 역분개 | team14_persistent.py; CI 10차 미확인 | 완료 수업 환불의 3종 역분개 | 13 |
| 116 | 10% | 실지급 차단 | 지급 후 회수·잔액 정책 | team14_persistent.py; CI 10차 미확인 | 지급 후 회수·잔액 정책 | 사장 |
| 117 | 0% | 없음 | 제재/이의 신청 | team14_persistent.py; CI 10차 미확인 | 제재/이의 신청 | 사장 |
| 118 | 0% | 없음 | 양측 진술·운영 판단 | team14_persistent.py; CI 10차 미확인 | 양측 진술·운영 판단 | 13 |
| 119 | 10% | 모의 환불 상태 | 보강/교체 UI·정책 | team14_persistent.py; CI 10차 미확인 | 보강/교체 UI·정책 | 13 |
| 120 | 60% | 반올림·부분 환불·재시도 테스트 코드 | 실제 CI/지급 후 취소 | team14_persistent.py; CI 10차 미확인 | 실제 CI/지급 후 취소 | 15 |
| 121 | 20% | KRW 검증·비교 필요 명시 | 국가·PG·세무 후보 | team14_booking_events.py / team14_persistent.py; CI 10차 미확인 | 국가·PG·세무 후보 | 외부 |
| 122 | 10% | 실 API 비활성 | 승인된 PG sandbox | team14_booking_events.py / team14_persistent.py; CI 10차 미확인 | 승인된 PG sandbox | 사장 |
| 123 | 40% | 예약 이벤트 모의 상태 | 실제 PG 실패/시간초과 | team14_booking_events.py / team14_persistent.py; CI 10차 미확인 | 실제 PG 실패/시간초과 | 13 |
| 124 | 50% | 이벤트/거래 중복·영속성 | 서명·순서·재처리 | team14_booking_events.py / team14_persistent.py; CI 10차 미확인 | 서명·순서·재처리 | 13 |
| 125 | 10% | 카드 정보 저장 안 함 | 안전 PG UI | team14_booking_events.py / team14_persistent.py; CI 10차 미확인 | 안전 PG UI | 사장 |
| 126 | 10% | 지급 차단 | KYC·국가·세무 | team14_booking_events.py / team14_persistent.py; CI 10차 미확인 | KYC·국가·세무 | 외부 |
| 127 | 10% | 미승인 요율 분리 | 주기·환전·최소액 | team14_booking_events.py / team14_persistent.py; CI 10차 미확인 | 주기·환전·최소액 | 사장 |
| 128 | 50% | 원장 보존식·SQLite 재개방 테스트 | 실 PG 대사·CI | team14_booking_events.py / team14_persistent.py; CI 10차 미확인 | 실 PG 대사·CI | 15 |
| 129 | 0% | 없음 | 명세/영수증 구조 | team14_booking_events.py / team14_persistent.py; CI 10차 미확인 | 명세/영수증 구조 | 13 |
| 130 | 10% | 실거래 API 비활성 | 승인·외부심사·실제 연동 | team14_booking_events.py / team14_persistent.py; CI 10차 미확인 | 승인·외부심사·실제 연동 | 사장 |

## 점수 기준 및 과대평가 방지
0=미착수, 10~30=준비/계약/후보, 40~60=부분 구현/주요 기능, 70=모의 원장 구현+검증 보완, 80 이상은 실제 연결 및 검증 증거 요구. 본 팀은 실제 Team13 서버와 미연결이므로 80 이상 없음. 'CI 미확인'은 10차 신규 변경에 대한 의미이며 이전 차수 HQ 성공 보고를 부정하지 않는다.

## 10차 실제 연결 조건 (총괄본부 → 11·13번 요청)
1. Team13에서 **서버가 인증한 내부 이벤트**를 생성하고, `booking_id, month_id, lesson_id, event_id, transaction_id, action, booking_status, currency, amount_krw` 제공.
2. Team13 서버 소유 예약 조회자 `resolve_booking(booking_id)`가 `booking_id,month_id,lesson_id,learner_id,teacher_id,teacher_approved,booking_status,authenticated_event` 반환. 값은 클라이언트 JSON이 아닌 **서버 DB/검증된 내부 컨텍스트**에서 유래해야 함.
3. 11번은 역할별 승인·예약 소유권·교사 자격 취소 시 기존 예약의 처리 규칙 확정. 단순 boolean `teacher_approved`는 임시 계약으로 실제 역할별 승인 범위 필요.
4. Team14의 `apply_verified_booking_event`는 외부 webhook/HTTP endpoint가 아니라 신뢰된 내부 호출 전용. 13번 실제 서버 호출·운영 배포는 미실시. 15번이 별도 브랜치 조합 후 E2E 검증 필요.
5. 완료 후 환불 시 강사/소개/플랫폼 발생분의 역분개는 아직 미구현. 현 원장은 완료된 회차 환불을 거부하며, 115번을 완료 처리할 수 없음.

## 검증 및 변경
- 문법 검사 우선: `python -m compileall -q phase3/team14*.py phase3/test_team14*.py` (shell 확장 확인 필요).
- 테스트: `python -m unittest discover -s phase3 -p 'test_team14*.py' -v`.
- Actions: https://github.com/anigio2705-dev/hangeul-swipji/actions/workflows/team14-monthly-tests.yml
- 10차 GitHub Actions 실행 SHA·run URL·exit code: 미확보. **52개 통과 주장 금지**.
- 실 결제·송금·환불 API/운영 서버/타 팀 브랜치/main 변경 없음.

## 총괄본부 승인 요청
- 부서: 14 사업 시스템팀.
- 내용: Team11/13 인증된 내부 완료·취소 이벤트 및 역할 승인 계약 확정, 15번 독립 실행 검증, 미승인 보상·환불 정책 취합.
- 이유: 실제 예약 데이터 조회자와 이벤트 인증 없이 모의 정산을 공개 연결하면 위조 정산 가능.
- 위험: 위조 수업 완료, 중복 거래, 과다 보상, 법률/세무 위험.
- 미승인 영향: 서버 연결·실금전·정책 확정 HOLD, 독립 개발 지속.
- 권장안: Team13이 서버 조회 계약을 제공한 뒤 15번이 안전한 테스트 DB에서 연결 검증. 금전 정책은 총괄본부가 사장에게 취합.
