# 실제 화면·저장·계정 분리 검사와 진술 화면 수리

2026-11-17 KST. 이전 복사본 검사에 이어 실제 Playwright Chromium 및 독립 검토를 수행했다.

## 최종 판정

**이번에 정한 로컬 시험 범위는 통과했고 독립 검토도 ACCEPT다.** 실제 화면에서 제품 결함1건(서버가 요구하는 상대방 진술을 입력할 UI 누락)을 찾아 수리했다. 제품 변경은 phase3/app.js의 기존 진술 API 화면 연결뿐이다. 원래 서버의 본인/관리자/비참여자 권한, 진술 요건, 환불·승인·원장 로직은 변경하지 않았다.

- 원본 제품 기준: 94a40b84c4c5665b5964b47f128b9472cfdae6eb.
- 이전 시험·fixture 코드: fd7b3ae5752e12cc3cb4f624814cd8d7a9c51490.
- 최종 app.js SHA256: 1254ad0d1698541a8a67a6ad287c2d8c6425108fcab20d062dc7d040fef5ba24.
- 최종 browser-test.cjs SHA256: 9c392980d4018745e837656a09231ed9706aa2598fe95ee00e7847beec8c46de.
- 독립 판정: ACCEPT_SCOPED_FIXTURE_REPAIR_STATEMENT_UI_STORAGE_AND_ACCOUNT_ISOLATION. independent/REVIEW.md와 REVIEW.json 참조.

## 실제 브라우저 환경

프로젝트 lockfile의 Playwright1.51.1 공식 Chromium Headless Shell134/build1161을 사용자 캐시에 설치했다. 기존 full Chromium의 ProcessSingleton UNIXsocket 실패와 달리 정상 시작됐다. sandbox/네트워크/권한 설정을 낮추지 않았다.

처음 CDN ZIP 다운로드가 유효하지 않았고 설치기의 공식 대체 미러에서 브라우저/FFmpeg 설치가 완료됐다. 최초 오류부터 최종 설치 원문은 headless-shell-install.log에 보존했다. 별도 운영 서버/새 유료 자원은 만들지 않았다.

모든 제품 시험은 disposable loopback/SQLite와 시험 계정으로 실행했다. TLS 시험은 기존 browser_server.py의 임시 자체 서명 시험 인증서를 사용했다. 브라우저 게이트·앱 계정·관리자 계정은 서로 구분했다. 원격 운영 Auth/결제/DB는 연결하지 않았다.

## 발견한 제품 결함과 수리

실제 화면에서 가입→강사 승인→가능시간→예약→모의결제→과제/피드백→출석/완료→모의정산은 진행됐지만, 신고 후 관리자 환불은 상대방 본인 진술이 없어 거절됐다. app.js에는 진술 조회·저장 UI가 존재하지 않았다. API 검사만으로는 사용자가 이 단계에 도달할 수 없는 문제가 드러나지 않았다.

수리:
1. 예약 당사자의 ‘신고 진술 확인·추가’ 버튼과 진술 목록·본인 입력창을 연결했다.
2. 관리자는 ‘진술 확인’으로 읽기만 가능하며 저장창이 없다. 직접 관리자 POST 역시 기존 서버에서403이다.
3. 입력은 기존10~5000자 규칙을 적용하고 원문은 textContent 기반의 기존 el()로 표시한다.
4. 계정·화면·account generation을 고정하여 계정 전환/로그아웃 뒤 늦은 응답이 화면을 열거나 저장 완료로 오인되지 않게 한다.
5. 서버 정책이나 검사 기준을 낮추지 않고 실제 교사 계정에서 진술을 저장한 뒤 같은 환불·이의신청 흐름을 재실행했다.

수정 전 원문: browser-staging-after-selectors.log. 수리 후 원문: browser-staging-verified.log. statement-ui.patch 및 REPAIR_SCOPE.md 참조.

## 실제 검사 결과

| 검사 | 결과 | 정확한 범위 |
|---|---|---|
| 통합 HTTPS 화면 검사 |34확인 PASS, JS오류0 | 실제 가입/로그인/승인/예약/모의결제/과제/피드백/진단/출석/완료/모의정산/진술/환불/이의신청/재예약 |
| PC·모바일 |1440·390px PASS | 실제 Chromium 에뮬레이션. 홈페이지 유지, 핵심 화면 및8언어에서 문서 가로 넘침 없음 |
| 전문 교재 |96교재×2폭=192 dialog PASS | 학생에게 질문288개/폭 표시, 정답해설0; 승인 강사 지도 화면 확인 |
| 무료 학습 |350단원×2언어=700보기 PASS | 모든 단원 실제 브라우저 렌더, JS오류0 |
| 무료 읽기 |600항목 PASS | 내용·퀴즈 브라우저 감사, 실패0 |
| 무료 기능·음원 |PC/모바일 모두 PASS | 언어·진도저장·퀴즈·읽기,78MP3 ended 이벤트/폭,404·취소 경계. 발음 청취 품질 승인 아님 |
| 즉시 대화 |10확인 PASS | 두 계정 opt-in→매칭→양측확인→같은 모의Jitsi방→종료·만료, 요청에 게이트 인증 누출 없음 |
| 기기·영상 UI |16확인 PASS | 합성 카메라/마이크, 권한거절·늦은 stream 정리·재연결·mock provider iframe. 실제 두 기기 통화 아님 |
| 기존 Python |92개 PASS | app.js 수리 후 실제 회귀 재실행, 앞선92와 중복 합산하지 않음 |
| 기존 UI시간대 모형 |exit0 | 원래 VM 회귀 유지, 실제 화면의 프로필NY/deviceHonolulu 및 저장UTC 불변 확인 별도 |
| 독립 HTTP 부정 검사 |4개 PASS | 타인 진술 위조 거부, 동일환불ID 다른금액 거부/원장불변, 계정별 프로필/진단 분리, 로그아웃세션 재시작 후 거부 |
| 독립 실제 프로필 UI |6확인 PASS | 두 browser context UI가입·저장·새로고침·API·읽기전용 SQLite 대조·390px |
| 독립 실제 진술 UI |6확인 PASS | 비참여자403, 본인저장, 새로고침보존/문자열XSS비실행, 관리자읽기전용/POST403, 실제로그아웃 뒤 늦은응답차단 |

확인 항목·test method·단원 수를 하나의 ‘총 검사 수’로 더하지 않았다. 출석30분은 원래 시험용 파일 시계로 진행하며 실제30분 수업 증거가 아니다.

## 기존 브라우저 fixture 보완

제품 결함 외에 구형 browser-test.cjs의 기대값3개가 현재 계약과 달랐다. 최초 실패 원문을 보존하고 아래처럼 보완했다.
- 가능시간과 새 휴무 폼에 name=start/end가 겹쳐 strict locator가 실패했다. ‘가능 시간 저장’ 버튼을 가진 form으로 범위를 고정했다.
- 기기 locale 시간 문자열을 찾던 검사는 현재 참여자 프로필 시간대 계약과 달랐다. 실제 학습자 timezone을 New_York로 저장한 뒤 기기Honolulu에서도 NY표시와 원래UTC 불변을 확인한다.
- 학생 교재에 정답 details3개를 기대하던 검사는 현재 정답 숨김 정책과 충돌했다.192개 dialog에서 정답details0·질문3개·정답해설제목0을 확인하도록 강화했다.

학생 정답을 다시 공개하거나 서버 권한을 완화해서 검사를 맞추지 않았다. 독립 검토자가 해당 보완을 확인했다.

## 보존·재현

개발자가 작성한 검증과 독립 검증 원문은 구분했다. independent/ 아래 보고서·실행로그·별도 스크립트·SOURCE_BINDINGS/MANIFEST에 독립 소스 바인딩이 있다. 대표 화면 스크린샷 및 SCREENSHOT_MANIFEST.json을 보존했다.

저장소 루트에서:
```sh
npm ci --prefix phase3 --ignore-scripts
./phase3/node_modules/.bin/playwright install chromium --only-shell
node phase3/browser-test.cjs --staging
node phase3/browser-test.cjs --staging --video-only
node phase3/instant-browser-test.cjs
NODE_PATH="$PWD/phase3/node_modules" node scripts/browser-smoke-phase2.cjs
NODE_PATH="$PWD/phase3/node_modules" node scripts/browser-functional-phase2.cjs
NODE_PATH="$PWD/phase3/node_modules" node scripts/browser-audit-reading-600.cjs
NODE_PATH="$PWD/phase3/node_modules" node scripts/browser-audit-lessons.cjs
python -m unittest discover -s phase3 -p 'test_*.py' -v
```

독립 스크립트는 HS_REVIEW_SOURCE에 이 checkout 절대경로를 지정해 실행한다. 운영 계정·외부 서비스 자격증명이 필요하지 않다. 기존 감사 스크립트가 갱신한 tracked 결과는 이 보고서 경로로 회수하고 이전 원문으로 복구했다.

## 판정의 한계와 다음 작업

이것은 실제 브라우저를 포함한 **한글쉽지 현재 후보의 지정된 로컬 기능·저장·계정 분리 검증 통과**이다. 전 제품의 영구 무결점, 실제Android/iPhone, 두 기기 음성/영상, 유료결제/정산, 운영 Supabase, 다중호스트/대규모부하, 교육효과·교사청취승인, 운영배포 또는24시간시험 통과를 의미하지 않는다.

기존 운영24시간 시험·서버 설정·원장·요청·예산은 변경하지 않았다. 이번 모델 호출0, 새 Cloud workflow0, 새 유료 자원0, main 병합0. 코드 수리본은 이 시험 branch에만 보존하며 운영 반영은 별도 완료 조건이다.

