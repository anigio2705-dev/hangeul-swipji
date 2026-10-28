# 12차 품질·운영팀 — 독립 회귀 및 160개 수행률 상태

## 실제 변경
- .github/workflows/team15-independent-regression.yml 의 팀11/12/13/14 checkout SHA를 12차 조회 HEAD로 교체.
- 변경 커밋 11a920ff79b3a503f4849ca506c9da0882f0abec
- 고정 SHA: 11 1994f8f45a21d2f73269934cd7703f54be1b7ffe, 12 e67d7d42db2ad6694a1081cd03659282bea28df3, 13 874890f35b4496fd9cba0b485556971fa7bb20c6, 14 a0fdc31ab4f1202770665d2735ab4bef69b2002b.
- 기존 독립 검사 7개 job 및 Team14 전체 test_team14*.py 탐색 유지.

## 확인된 실제 실패
- Team14 Actions https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40617308413: 문법 검사 성공, 전체 회귀 test job 실패. 본 실행은 11차 환불 7개 중 4개 오류 보고와 일치하지만 로그를 통해 4개 각각의 스택을 재확인하지는 않았음.
- 위 실패는 **과거 실행**이다. 최신 14번 SHA가 같은 실패를 재현하는지는 별도 Actions run 확인 필요.
- 새 SHA에 대한 Team15 독립 workflow run URL, 통과/실패 job 수는 아직 확보되지 않음. PASS 선언 금지.

## 160개 수행률
10차 원본 160개 점수: docs/team15/TENTH_PASS_160_PROGRESS_CALCULATION_20261028.md, 전체 30.38%, 11 45.00%, 12 36.33%, 13 26.00%, 14 25.67%, 15 14.00%. 이는 **10차 잠정 기준선**이지 12차 확정 수행률이 아님.
12차 최신 팀별 항목 점수와 최신 SHA 코드-검사 근거가 전부 재취합되지 않았으므로 12차 새 전체 평균/증가분은 미확정. 131~160은 이번 CI 설정 변경만으로 점수를 올리지 않고 10차 보수적 추정 유지.

## 통합 검증 HOLD
- 11→13 서버 DB 사용자/승인/예약 소유권을 예약·화상 API에 실제 연결했는지.
- 12→13 무료 진도/검색 필터/예약 라우팅을 실제 로그인 세션으로 통과하는지.
- 13→14 서버 인증 완료·취소 이벤트, 멱등 원장, 3자 역분개 및 DB 재시작 복원을 단일 비운영 서비스로 검증했는지.
- 실제 PC/모바일 양방향 A/V, 음원 사람 청취, 운영 배포 및 실제 결제는 별도 HOLD.

## 다음 작업 및 팀별 요청
P0 Team14: 최신 SHA 전체 회귀 run URL, 7개 환불 테스트 통과 수, 금액·미인증·중복 거부 로그 제공. Team13: 인증된 이벤트/예약 조회 인터페이스 및 Team11 서버 권한 적용 근거. Team12: 실제 로그인 후 강사 검색·예약 E2E. Team11: 서버 DB 기반 권한·복원 E2E. Team15: 최신 독립 workflow 실행 결과 확인, 합성 데이터 비운영 통합 테스트 구축, 131~160 실제 기능 점수 재평가. 동일 실패가 반복되면 입력 이벤트 정규화와 refund_completed/refund 계약을 비교해 원인 변경.
No main merge, other-team code edits, live payment, production DB or deployment.
