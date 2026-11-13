# Q007 / 원본45 — 한 과제 수정·격리검사 후 정지

2026-11-13 KST. 이번 사용자 지시: 보류 과제 하나를 처리하고, 30분 전에 결과와 재개점을 기록한 뒤 멈춘다. 다음 과제나 무제한 자동화를 시작하지 않는다.

## 시작 근거와 범위

- #305의 272개 댓글을 실제 조회했다. Q007 시작은 댓글6816682818, 격리 상태는6817290711, STEP10_VALIDATION_20261112.json에서도 원본45/Q007 QUARANTINED를 확인했다.
- Q001~Q006을 다시 실행하지 않았다. 최신 수락 Q052의 누적 소스 ca4874635582acfffd70e3f94959a1af91d8e2fd를 입력으로 고정했다. 원격 work/backlog-q052 HEAD와 일치한다.
- Q007의 최초 입력398a10f6270f35bd8e6e1c5a5f804285317b0629와 최신 수락 입력의 intro.html은 같은 blob c97615859937253c6c9028b4b33a16d8a36169c7이다. 기존 수락된 이 파일의 후속 변경을 덮어쓰지 않았다.
- 루트 AGENTS.md·GLOBAL_MASTER_PLAN.md·DEVELOPMENT_STATUS.md 및 교육 기준5문서를 읽었다. 통합 브랜치 HEAD2ca95fa1aa8206ec8763443d8256ab54ac789017도 별도로 조회했다. 누적 자동개발24건을 보존하기 위해 이번 수정안은 Q052에서 분기하며 통합 브랜치를 갱신하지 않는다.
- Render exec10 get_service에서 suspended=suspended, suspenders=[user], autoDeploy=no/trigger=off를 확인했다. 서비스·AS·예약을 재개하지 않았다.

## 확인한 결함과 확인하지 못한 원인

현재 제품 코드의 기능 누락은 확정했다. units[*].quiz의258문항은 질문·번역·선지·정답 인덱스 네 필드뿐이었고, renderQuiz는 정답만 표시했다. 한영 근거 해설 데이터와 일반 채점/오답 복습 표시가 없었다. 원본에 같은 회귀 검사를 실행하면 첫 단원부터 expected5 explanations, got0으로 실패한다(BASELINE_FAIL.log).

과거 Q007의 실행기 실패 원인은 아직 확정하지 않았다. Q007 원본 후보·B검사 계약·REJECTION·raw·attempt는 중지된 서버 디스크에 있고 이번 회차에서 읽지 않았다. GitHub에 게시된 Q007 후보 브랜치도 검색에서 발견되지 않았다. 새 검사와 새 수정안을 과거 C/B 결과의 복원으로 표현하지 않는다. 관련 과거 파일을 삭제하거나 초기화하지 않았다.

## 수정

- intro.html의 모든50단원·258문항에 한국어/영어 근거 해설을 다섯 번째 필드 q[4]로 추가했다.
- 자모 결합, 초성·모음·받침, 받침 제거, 자음 이름, 음절 수, 낱말 뜻과 상황 인사의 근거를 문항별로 제시한다. 밤처럼 여러 뜻이 있는 낱말은 이 단원에서 쓰인 뜻으로 한정했다.
- 같은 renderQuiz 결과 표시를 사용하므로 일반 채점과 오답 복습에 모두 적용된다. textContent로 출력한다.
- 기존 문제·선지·정답·순서·교재와 퀴즈 외 코드를 보존했다. 해설 필드 제거 후 원본 JSON deep equality, 렌더러 한 지점 변경을 역변환한 전체 나머지 소스 동일성도 검사했다.

## 실제 검사와 한계

1. 원본: 동일 Node DOM 검사로 해설 누락 FAIL 재현. 환경 실패와 구분해 BASELINE_FAIL.log에 보존했다.
2. 수정본: Node + DOM simulation,300개 채점/복습 흐름·2,019 checks PASS(TEST.log). 50단원258문항×한영, 미응답, 전부정답/오답, 복습 제거, 점수·완료·저장, 재도전·중복제출 방지, 원본 보존, textContent 안전 출력 포함.
3. 한 과제 제한:8개 격리 시험 PASS(GUARD_TESTS.log). 성공/실패/시간 초과, 중복잠금, 충돌·재시작 시 재실행 거절, 다른 과제·SHA 거절, 실행시간 한도, 실행 중 소스변경을 확인했다.
4. 실제 제한 실행: REQUEST→STARTED→TEST.log→RESULT의1회 실행 PASS_STOPPED. 종료 후 같은 실행을 다시 시도했을 때 NO_REPLAY로 거절, 기존 RESULT 바이트 불변(REPLAY_REFUSAL.log).
5. 실제 Chromium: 설치된 Playwright의 기본 브라우저 부재를 확인한 뒤 /usr/bin/chromium을 시도했다. socket() Operation not permitted로 페이지 로드 전 실패했다(BROWSER_ENVIRONMENT_FAIL.log). 브라우저·모바일 레이아웃 PASS를 주장하지 않는다. 별도 test-q007-browser.cjs를 지원 환경용으로 남긴다.
6. 최초 RESULT.scope 메타데이터가 LOCAL_BROWSER_VERIFICATION_ONLY였으나 실제 실행은 Node DOM simulation이다. 원본 영수증을 수정하지 않고 EVIDENCE_SCOPE_CORRECTION.json으로 정정했으며 실행기 새 출력 라벨도 고쳤다. TEST.log의 real_browser_verified=false가 실제 범위다.

## 단일 실행 장치의 정확한 범위

scripts/run-one-q007.py는 이번 로컬 Node 검사 하나만 허용하는 제한 실행기다. task=Q007/original45/inputSHA·source/testSHA를 결속하고, STARTED 또는 RESULT가 있으면 재실행하지 않는다. 프로세스 최대120초·승인 시각으로부터 최대25분 기한을 검사한다. 성공·실패·시간초과 모두 종료 결과를 저장한다. 다음 과제 선택기, 서버 모델, AS나 원격 쓰기 경로를 호출하지 않는다.

이는 기존 Render 연속 실행기에 단일 과제 종료 계약을 설치·검증했다는 뜻이 아니다. 서버 전체 Resume를 허용하지 않는다. 이번 실행은 새로운 한정 로컬 검증이며 서버 B의 독립검사·A수락·D영속기록을 대체하지 않는다.

## 현재 판정과 다음 재개점

**Q007 수정안 및 로컬 격리검사 완료 / 서버 재처리·독립 B·A·D 미완료 / 전체 중지 유지.**

- 기존 수락24/160, 보류 기록32, Q053 소유자HOLD 및 서버 cursor·D·baseline은 변경하지 않았다. 수락25로 올리지 않는다.
- 다음 과제를 실행하지 않았다. 새 유료 자원·운영DB·main·통합 브랜치·제품 배포·AS·예약은 변경하지 않았다.
- 이 회차의 서버 모델 호출0. 이 Work 대화 자체가 무료라는 주장은 하지 않는다.
- 후속 회차: 이 수정안의 커밋·해시·TEST.log를 재사용한다. 서버의 Q007 기존 후보·독립 B 계약·실패 원본을 읽을 수 있는 안전한 경로를 먼저 마련하고 대조한다. 원본 B 계약을 약화하거나 옛 후보를 최신 소스에 무조건 덮어쓰지 않는다.
- 서버 작업이 필요하면 기존 OWNER_STOP 표식과 다음 과제 생성을 차단할 서버 수준 종료 계약을 먼저 결속해야 한다. 이번 로컬 제한기를 서버 종료 계약으로 오인하지 않는다.
- 실제 브라우저·교육 검수·배포는 미완료다. 그 뒤에 실제 B→A→D 판정을 받아야 보류 해소 및 수락 집계를 변경할 수 있다.

## 재현 명령

격리 검사: `node scripts/test-q007-explanations.cjs intro.html`

제한기 회귀: `python3 scripts/test-q007-guard.py -v`

기존 REQUEST 폴더로 제한기를 재실행하면 거절되는 것이 정상이다. STARTED/RESULT를 지우지 않는다. 이후 새 실행이 승인되면 새로운 증거 폴더·새 기한·정확한 해시를 갖는 요청을 사용한다.
