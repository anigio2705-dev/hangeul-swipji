# Team14 — 12차 오류 수정·수행률 보고 (2026-10-28)

## 원인과 수정
- 11차 GitHub Actions run `40617308413`에서 신규 환불 테스트 7개 중 4개 오류가 총괄본부에 보고됨. 실행 로그 원문은 이 보고 작성 시 별도 확보하지 못했음.
- `phase3/team14_persistent.py`: 이벤트 종류 검사와 양수 금액 검사는 `refund_completed`를 허용했으나, 바로 다음 `if action!='refund' and amount_krw!=0` 조건이 완료 수업 환불을 잘못 차단. `if action not in ('refund','refund_completed') and amount_krw!=0`로 수정.
- 기존 `refund` 처리, `complete`/ `cancel`의 금액 0 조건, 중복 거래 ID/operation ID, 예약 식별자 및 상태 검증은 유지.
- `phase3/test_team14_refund_event_validation.py`: 양수 완료 환불, 0·bool·과다 금액 거부, 잘못된 이벤트 거부, 재전송 멱등성, 완료 이벤트의 잘못된 금액 거부 등 7개 추가.
- `.github/workflows/team14-monthly-tests.yml`: 문법 검사 선행, 기존 59개와 신규 7개 총 **66개 테스트 코드 예상**. 테스트 삭제 없음.

## 자동 검사
- GitHub Actions: https://github.com/anigio2705-dev/hangeul-swipji/actions/workflows/team14-monthly-tests.yml
- 12차 수정 SHA의 Actions 성공 실행 URL·로그·종료코드는 현재 **미확보**. 66개 테스트 **성공 판정 보류**. 기존 run `40617308413` 실패 사실은 유지.
- 실제 두 브랜치 통합·서버 API 테스트·실제 결제/송금/운영 배포 미실시.

## 101~130 개발 수행률
- 11차 제출: 795/30 = **26.5%**.
- 12차 잠정: **26.5% 유지** (변경 +0.0%p). 오류 수정 및 테스트 보강은 이미 11차에서 점수를 반영한 기능의 정상화 작업으로, 자동 검사·실제 연결 증거 없이 수행률 상향하지 않음.
- 101~130 개별 점수는 `docs/team14/ELEVENTH_PASS_PROGRESS_20261028.md` 표의 11차 열과 동일. 원본 번호와 증거 기준 유지.
- 160개 전체 수행률은 15번이 각 팀 점수를 취합하여 산정. 10차 전체 잠정 30.38%와의 비교는 15번 담당.

## 팀 간 연결
- Team11: 서버 DB 기반 로그인/강사 승인/예약 소유권 확인 계약.
- Team13: 내부 이벤트 인증과 `resolve_booking` 서버 조회 계약, 수업 완료·취소·환불 이벤트 전달. 현재 Team14 `team14_verified_bridge.py`는 신뢰된 내부 호출용으로만 구현; **실제 Team13 서버에 배선되지 않음**.
- Team15: 수정 SHA의 Actions 로그 및 66개 회귀 테스트 독립 확인, 비운영 환경에서 Team11/13/14 통합 검증 요청.

## 남은 오류·다음 작업
1. GitHub Actions 문법 검사 및 전체 66개 테스트 실제 실행 결과 확보. 실패가 있으면 해당 테스트 이름과 traceback 기준으로 재수정.
2. Team13 실제 이벤트와 인증 서버 조회를 비운영 환경에서 연결.
3. 완료 수업 환불의 3자 역분개·부분 환불·반올림·파일 DB 재시작 검증 결과 확인.
4. 실금전 및 운영 배포는 대표 승인 전까지 비활성.
