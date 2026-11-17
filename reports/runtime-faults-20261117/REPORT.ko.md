# 추가 장애·지연응답 검사와 프로필 화면 수리

2026-11-17 KST. 대표님 후속 지시: 필요한 검사를 별도 환경에서 추가 시행한다.

## 결과와 수리

이번 추가 로컬 검사 범위는 통과했다. 프로필 저장 응답이 늦게 도착할 때 로그아웃 화면 또는 새 사용자 화면이 이전 사용자로 돌아가는 화면 결함 1건을 재현·수리했다. 서버 세션의 권한 상승이나 다른 계정 DB 덮어쓰기는 관측하지 않았다. 서버 /api/me와 화면 계정이 서로 다름을 실제 Chromium으로 대조했다.

기준 커밋은 a0fae280cf6f03e9959be99349ee33841eda3ee0(PR345 최종 수리본)이다. 제품 변경은 phase3/app.js의 프로필 저장 응답 처리 한 곳이다. 저장 시작 시 사용자 객체·화면 세대·계정 전환 세대를 고정하고, 응답 및 오류가 돌아올 때 현재 계정/화면인지 확인한다. 응답의 사용자 ID도 같아야 반영한다. 이미 서버에 정상 저장된 이전 계정의 프로필은 유지하며, 늦은 응답이 새 화면이나 성공/오류 메시지를 바꾸지 않는다. 서버·권한·원장 코드는 변경하지 않았다.

## 실제 실행 결과

| 시험 | 결과 | 확인 내용 |
|---|---|---|
| 모의결제 commit 직전 SIGKILL | PASS | 미커밋 변경 롤백; 8개 동시 재시도에도 charge 1개 |
| 모의결제 commit 후 응답 전 SIGKILL | PASS | charge 보존; 재요청 후 6개 표 원문 불변 |
| 모의환불 commit 직전 SIGKILL | PASS | 6개 표 원문 불변; 재시도 1회만 반영 |
| 모의환불 commit 후 응답 전 SIGKILL | PASS | 8개 동시 재요청 모두 duplicate=true; 6개 표 원문 불변 |
| 실제 Chromium 지연 프로필 3상황 | 수정 전 3 FAIL → 수정 후 3 PASS | 로그아웃 후 성공 응답, Bob 로그인 후 Alice 성공 응답, Bob 로그인 후 Alice 오류 응답 |
| 정상 프로필 실제 화면 | 6확인 PASS | 저장·새로고침·다른 계정 불변·API·SQLite 대조·390px |
| 기존 진술 실제 화면 | 6확인 PASS | 본인 저장·권한 차단·지연응답 차단 |
| 통합 HTTPS 실제 화면 | 34확인 PASS, pageerror 0 | 가입→예약→모의결제→과제/피드백→진술→환불→이의신청→재예약, 96교재 두 폭 등 |
| Python 회귀 | 92개 PASS | python-regression.log |
| UI 시간대 VM 회귀 및 app.js 구문 | exit 0 | timezone-regression.log; node --check phase3/app.js |

6개 표는 ledger, local_refund_requests, local_refund_adjustments, disputes, bookings, audit이다. 단원/dialog 수와 검사 개수를 합산하지 않는다. 최초 crash 시험의 4개 오류는 재시작 때 시험용 관리자를 중복 생성한 harness 초기화 문제였다. 계정 존재를 확인하도록 시험 harness를 고쳐 최종 4개가 통과했다. 최초 오류 원문도 보존했다.

## 장애 주입과 검증 범위

시험 자식 프로세스는 실제 제품 HTTP route와 SQLite를 실행한다. 시험 전용 Connection.commit을 저장 직전에 정지시키거나 Handler.send를 실제 commit 후 응답 직전에 정지시켰다. 부모 시험기가 해당 자식 PID에 SIGKILL을 보내 실제 종료 -9와 요청 단절을 확인하고, 같은 임시 DB로 새 PID를 시작했다. 매번 SQLite integrity_check=ok, foreign_key_check 빈 목록, 기존 학습자 세션을 확인했다. 새 장애 시험은 실제 로컬 시각을 사용한다.

이는 **시험기가 재시작한 복구 검사**다. ABCD/AS 자동 감지·자동 재시작, 호스트/디스크 소실, 분산 서버, 운영 배포 또는24시간 운행 합격의 증거가 아니다. 기존24시간 시험·Render·운영 DB·실결제·모델·새 유료자원 변경0. 모든 계정과 금액은 폐기 가능한 시험 자료이며 서버·브라우저·임시DB는 종료·정리했다.

브라우저 race 시험은 실제 서버의 프로필 PUT을 완료한 뒤 응답 전달만 늦췄다. 실제 로그아웃/Bob 로그인을 수행하고 응답을 반환했다. Alice의 변경이 Alice DB에 정상 저장됐는지 읽기전용 SQLite로 대조했다. 오류 사례는 실제 성공 PUT 대신 시험기가 합성500을 전달했으므로 DB 저장 실패를 의미하지 않는다.

## 검토·재현·재개 지점

새 수리는 이 작업자가 작성·검사했다. 과거 독립 검토자가 작성한 정상 프로필/진술 브라우저 스크립트를 임시 폴더로 복사해 현재 소스에서 재실행했다. 기존 independent/ 증거와 판정은 보존했다. **이번 변경에 대한 새로운 독립 B 수락을 주장하지 않는다.**

```sh
npm ci --prefix phase3 --ignore-scripts
./phase3/node_modules/.bin/playwright install chromium --only-shell
python reports/runtime-faults-20261117/test_crash_boundaries.py
node reports/runtime-faults-20261117/browser_profile_races.cjs
node phase3/browser-test.cjs --staging
node phase3/test_q002_timezone_ui.cjs
python -m unittest discover -s phase3 -p 'test_*.py' -q
```

browser_profile_races.cjs는 HS_RACE_OUTPUT으로 결과 경로를 지정할 수 있다. 전체 브라우저 검사가 생성한 phase3/staging-browser-results.json은 이 폴더에 복사하고 기존 tracked 원본을 복구했다. 기존 독립 스크립트는 이전 browser-followup-20261117/independent/ 아래 두 browser_*.cjs를 임시 폴더로 복사하고 HS_REVIEW_SOURCE를 현재 checkout으로 지정해 재현한다. 기존 증거를 덮어쓰지 않는다.

다음은 이 한정 수리본의 별도 코드 수락·통합 검토다. 실제 휴대전화·두 기기 통화·운영 Auth·실결제·교육 품질·운영 배포는 미완료다. 이번 시험을 이유로 기존24시간 운행이나 운영 설정을 바꾸지 않는다.
