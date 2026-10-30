# 11팀 모바일 음성 취소·백그라운드 재생 사례집 (2026-10-30)

## 계약·상태
- 160개 원장 관련: #58 모바일 실제 재생(외부/실기기 검증 관문), #59 실패 표시·재시도(12/15팀 원소유). 11팀은 공통 음성 엔진 하위 계약만 수정했으며 이 과제를 READY/DONE으로 임의 변경하지 않았다.
- 격리 브랜치: `team11/audio-gesture-20261030`. main, 운영 사이트, 테스트99 및 실금전 경로 미변경.
- **현재 상태: 코드 자체 회귀 검증 통과, 15팀 독립 감사/실기기 청취/통합·배포 승인 대기.** 실제 AI API 여섯 팀 연속 호출 및 두 개 READY 작업 자동 승계 실증과 구별한다.

## 사건 T11-AUDIO-CANCEL-20261030-01
- 사용자 현상: 모바일 페이지 이탈 중 `speechSynthesis.cancel()`이 동기적으로 `utterance.onend`를 발생시키면 `optionalSynthetic()`이 취소를 `tts-played`로 오인할 수 있다.
- 재현 환경: Node VM, SpeechSynthesis mock에서 `cancel()`이 즉시 `onend` 발생. 실제 iOS/Android 청취는 미검증.
- 기각된 기존 가정: 브라우저의 `cancel()`은 언제나 `onend`보다 먼저 반환한다.
- RED 테스트 커밋: `f866e069766478fc2d8f5b0380059573366dade1`, CI https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40994329890 (failure, 11팀 opt-in/user gesture 단계).
- 수정: `hangul-core.js`의 `stop()`에서 run 증가 후 먼저 `release()`를 호출하여 cancelled 상태를 확정한 뒤 `pause()`/`speechSynthesis.cancel()`을 실행. 동기 브라우저 이벤트는 중복 완료하지 못한다.
- GREEN 수정 커밋: `63b3b3dca1305a8bf25d572842367312732526ff`, CI https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40994363364 (success).
- 재사용 패턴: 비동기 완료 이벤트를 발생시키는 외부 cancel API보다 내부 Promise 종료 상태를 먼저 확정한다.

## 사건 T11-AUDIO-BACKGROUND-20261030-02
- 사용자 현상: `pagehide` 후에도 지연된 클릭 핸들러가 `play()`/`optionalSynthetic()`을 호출하면 사람 녹음이나 기기 합성음이 새로 시작할 수 있다.
- 재현 환경: Node VM, `pagehide` 이벤트 후 `document.hidden`이 아직 false인 경우와 hidden=true인 경우를 모두 확인. 실제 모바일 기기 검증은 미완료.
- 기각된 기존 가정: `pagehide`에서 한 번 `stop()`하면 이후의 새 재생 호출도 자동 차단된다.
- RED 테스트 커밋: `b72b9ff56ac3433d7c950d6a3281b578b980f38e`, CI https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40994396415 (failure).
- 수정: `hangul-core.js`에서 `play()`와 `optionalSynthetic()`이 `document.hidden===true || wasHidden`이면 `cancelled` 반환, Audio/TTS 생성 금지. BFCache/visibility 복귀 시에는 기존 `reloadManifest()` 재검증을 유지하고 새 사용자 탭을 요구한다.
- GREEN 수정 커밋: `2fa0d90eef02b5e1d6ee897e58138cbac1117b96`, CI https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40994424637 (success).
- 재사용 패턴: 브라우저 visibility 속성과 page lifecycle 플래그를 함께 검사하여 지연 이벤트에 의한 재시작을 차단한다.

## 협업·검증 요청
- **12팀:** #58/#59의 사람 녹음/보류/누락 음원 상태와 페이지 복귀 시 검수 상태를 확인하고, 사람 녹음과 기기 합성음을 절대 동일한 출처로 표기하지 않는지 교차 확인.
- **15팀:** 정확한 최종 SHA에서 실제 iOS Safari·Android Chrome의 페이지 이탈/복귀, cancel 동기 이벤트, BFCache, 재탭, 정상 사람 녹음, TTS 동의/철회, 회귀 및 음원 검수 보류 우회를 독립 검증. PASS/FAIL/재현 로그를 Issue #34에 등록.
- **중앙:** 160개 READY 및 팀 소유권 검증 후 #38(학습 진도 다중 기기 복원/권한) 또는 승인된 11팀 공통 기반 과제 배정. 이전 six-job #40973509528의 AI 호출 0건/READY 0 상태가 해결되지 않았다면 BLOCKED로 유지하고 실행기·큐를 교정할 것.

## 다음 실행 체크포인트
- 마지막 제품 수정 SHA: `2fa0d90eef02b5e1d6ee897e58138cbac1117b96`.
- 재현 후 수정된 실패: TTS 동기 cancel/onend 오인, 백그라운드 지연 재생.
- 11팀 자체 CI: 두 RED/두 GREEN 근거 위 참조.
- 남은 관문: 15팀 독립 실기기, 팀12 음원 정책, 전체 통합/Render99 데이터 영속성·백업·복원·롤백 및 대표 승인.
- 다음 선택 후보: 11팀 소유 공통 기반 #38 학습 진도 다중 기기 복원/권한 계약을 기존 코드·테스트에서 조사하고 안전한 격리 수정. 중앙 READY 검증 전에는 RUNNING/DONE 선언 금지.


## 사건 T11-TTS-WATCHDOG-20261030-03 — 15팀 반례를 11팀 제품에 인수
- 160개 계약: #58/#59 공통 음성 엔진 지원 범위. **원장 READY=0, DONE=0 유지**; 11팀 자체 수정으로 12팀 소유 계약을 완료 처리하지 않음.
- 교차 학습: 15팀 독립 감사 PR #119의 timeout→동기 onend 오인 사례를 확인하고, **11팀 최신 격리 HEAD에서 별도 재현**. 15팀의 선행 수정과 같은 안전 원리를 채택하되 11팀 HEAD의 새 테스트/커밋/CI로 별도 증명.
- 원인 가설 A: watchdog의 `speechSynthesis.cancel()`이 동기 `utterance.onend`를 발생시켜 실제 timeout이 `tts-played`로 오판됨. 가설 B: 타이머 미설정/누락. 가설 C: 재생 완료 뒤 오래된 콜백. 실제 RED에서 A 확인.
- RED: `tests/team11_audio_user_activation.test.cjs` SHA `e6cfcabcc7174fce6433cfd5b2ba635930284be0`; [Actions #40999984224](https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40999984224) FAILURE, expected `tts-timeout`, actual `tts-played` (기존 18 PASS, 신규 1 FAIL).
- FIX: `hangul-core.js` SHA `0567780e54298c5d733a202b74eaee6bb5b00b9a`; Promise timeout 결과를 먼저 확정하고 브라우저 cancel 실행. [Actions #41000021454](https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/41000021454) SUCCESS.
- 재사용 규칙: 외부 API의 cancel/close가 동기 완료 이벤트를 발생시키면 내부 Promise 종료 상태를 먼저 확정해야 함.
- 제한: iOS/Android 실제 기기 청취·12팀 원본 발음·15팀의 **최신 11팀 SHA** 독립 감사 미완료.

## 사건 T11-TTS-INPUT-20261030-04 — 다음 공통 음성 결함 자체 선정
- 현상: 공통 `play()`는 빈 값·비문자열을 `invalid`로 거부하지만 공개 `optionalSynthetic()`는 같은 값을 `SpeechSynthesisUtterance`에 전달하여 `tts-played`로 오판할 수 있었음.
- 원인 가설 A: 직접 TTS 진입점에 입력 검증 누락. 가설 B: opt-in 체크 누락. 가설 C: 음원 목록 보류 정책 우회. RED는 A를 확정했고 기존 B/C 경로는 유지.
- RED: 테스트 SHA `b9ad5396a9f04eea19358c23bfc868b624d98c75`, [Actions #41000056823](https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/41000056823) FAILURE: expected `invalid`, actual `tts-played`.
- FIX: `hangul-core.js` SHA `86f2088575c24e35e447907a13d83641138ac6bd`; 직접 TTS에서 빈 문자열·공백·null·undefined·배열을 거부. 명시적 동의, 검수 보류 차단, 사람 녹음 우선 정책 유지.
- GREEN: [Actions #41000097477](https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/41000097477) SUCCESS. 테스트 결과는 코드 기반 모의 브라우저 검사이며 실제 발음 청취를 인증하지 않음.
- 다음 작업: 11팀 소유 #38 다중 기기 진도·인증 권한 경계의 현재 API/클라이언트 계약 조사 및 테스트 가능한 후보 분리. 중앙의 의미계약·단일 소유권·15팀 독립 감사 전 READY/DONE 승격 금지.

## 2026-10-30 12:56 KST 실행 승계 체크포인트
- 현재 마지막 제품 변경 SHA: `86f2088575c24e35e447907a13d83641138ac6bd`; 최종 문서 커밋은 별도.
- 자체 RED→GREEN 두 건 확인. 15팀 PR #119의 timeout 반례를 11팀에 인수했으며 별도 #38 조사로 승계. 이것은 **중앙 READY 큐의 두 과제 자동 AI 호출/승계 성공이 아님**.
- 160개 원장 `automation/hq_backlog_160.md`: [x] 0개. `automation/hq_semantic_contract_paths.json`에서 READY 0; 실제 AI 호출 6-job 증거 [#40973509528](https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40973509528) 0회는 과거 실행의 실측이며 이 회차에 AI API 6팀 호출을 했다는 뜻이 아님.
- **11팀 직접 GitHub 파일 수정 및 CI만 실증**; 6팀 AI 모델 API 호출·READY 자동 승계 미실증, 중앙/15팀에 BLOCKED로 인계.
- 팀12 요청: 음원 출처/보류/누락/합성음 안내와 7일 학습 화면 계약 교차 확인. 팀15 요청: PR #83 최신 SHA 두 회귀 독립 검증, 실제 모바일 브라우저 청취, 15팀 PR #119과 중복 충돌 확인.
- 테스트99 실제 배포/현재 SHA/DB 영속성·백업·복원·롤백/대표 승인 미확인. main·운영 사이트·운영 DB·실결제·실송금 미변경.


## 2026-10-30 13:51 KST — 11팀 실제 연속 2작업 및 독립 반례 인수

- 원장 연결: #59(누락 음원 오인 방지·대체 안내, 12팀 소유/11팀 지원), #58(PC·모바일 재생, 12팀 소유/11팀 지원), #11(중앙 AI 실행기 작업 전 안전 검사, 11팀 소유). 본 기록은 어떤 번호도 READY/DONE으로 임의 승격하지 않는다.
- 작업 A, 15팀 독립 P0 반례 수용: 사람 녹음 '가'는 존재하고 '나'는 누락, 합성음 미동의 시 기존 11팀은 모든 재생을 막음. 가설 A=시퀀스 전체를 missing으로 처리하는 early return, B=검수 보류 음원 오판, C=기기 재생 실패. 15팀 RED #41004105104에서 A 확인 (Audio.play 호출 0 vs 1).
- 작업 A 실제 코드: 15팀 PR #123을 11팀 전용 격리 브랜치에 merge commit `69b7d25f3b5ca3cbbf16c8a73ed49b5f1aba7035`로 통합. `hangul-core.js`에서 실제 존재하는 사람 녹음만 부분 재생하고 `partial`/누락 글자를 명시. 보류 음원은 전체 차단, TTS 기본 OFF, 최신 watchdog/foreground/입력 검증 유지. `hangul-basics.html`·`hangul-week.html` 캐시 버전 갱신.
- 작업 A 독립 검증: 15팀 정확한 사전 HEAD `3cb7ca0d455be8baee055af4bc3aae782637d62c`에서 CI #41004193379 PASS. 통합 SHA `69b7d25`에서 11팀 #41005251399 PASS 및 15팀 독립 회귀 #41005257849 PASS.
- 작업 B, 자동 회귀 누락 자체 수정: 11팀 기본 workflow가 신규 15팀 동적 음성 회귀를 필수로 실행하지 않아 이후 수정에서 같은 오류가 재발해도 놓칠 수 있었음. 가설 A=워크플로에 테스트 경로·실행 단계 누락, B=Node 구문 오류, C=테스트 fixture 누락. workflow 직접 확인으로 A 확정.
- 작업 B 실제 코드: `.github/workflows/team11-audio-integration.yml`에 15팀 회귀 테스트의 push 경로, `node --check`, `node --test` 필수 단계 추가. 커밋 `b0771e5251f32e98a155b72430168a17f79eaf3a`; 동일 SHA 11팀 CI #41005283549 PASS, 15팀 독립 회귀 #41005288147 PASS.
- 원장 READY=0 / 기존 6팀 AI API 호출=0인 사실은 별도 BLOCKED. 이번 두 작업은 연결된 AI 호출 엔진이 자동 배정·승계한 결과가 아니라 GitHub 코드 작업과 CI에 의한 실제 연속 수정이다. 외부 AI API 호출 2개 과제 실증을 성공으로 주장하지 않는다.
- 12팀 요청: #58/#59 누락/보류/사람 녹음/합성음 표시와 실제 학생용·교사용 화면의 'partial' 반환 처리, 399조합의 음원 상태/사람 청취를 확인하고 근거 제출.
- 15팀 요청: 통합 후 11팀 정확한 SHA에서 iOS Safari·Android Chrome 실기기, 혼합 재생·보류 차단·TTS 동의/철회·캐시·BFCache를 독립 검증하고 #41000145711의 교육 원본 9개 불일치 원인을 12팀과 협력해 원본 보존 규칙을 약화하지 않고 해결.
- 중앙 요청: #11 READY 의미 검증/소유권 및 실제 6팀 API 호출=0 장애를 해결할 수 있는 승인된 통합 브랜치 작업 계약을 제시. 11팀은 다음 실행에서 중앙 READY·AI 호출 로그·#38 다중 기기 진도 인증 경계를 재조사한다.
- 테스트99: 배포 0회. Render99 SQLite 영속성·백업·복원·롤백 및 대표 승인 미확인. main/운영 홈페이지/실결제/실송금 미변경.
- 재사용 패턴: 독립 QA의 RED 테스트를 실제 제품에 인수한 다음, 해당 테스트를 제품 소유 팀의 CI 필수 게이트로 연결해야 이후 수정에서도 회귀 방지가 지속된다.
