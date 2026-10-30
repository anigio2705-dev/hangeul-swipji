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
