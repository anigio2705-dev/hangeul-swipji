# TEAM15-20261030-TTS-TIMEOUT — 실패→수정→독립 회귀

- 담당: 15 품질·운영 독립 QA / 협력: 11 공통 음성
- 160개 원장: #58 모바일 재생 검사, #59 실패 상태 표시 (지원 감사; READY/DONE 임의 변경 금지)
- 기준 브랜치: `team11/audio-gesture-20261030` at `8358a48bddf6f3b1d45c4aee5a459b0999ac7f39`
- 현상: 사용자가 선택적으로 활성화한 기기 한국어 TTS가 12초 후 시간 초과되어도 `speechSynthesis.cancel()`이 `utterance.onend`를 동기 호출하는 브라우저에서 `tts-played`로 오인.
- 초기 가설/실패 시도: 타임아웃 콜백에서 `cancel()` 이후 `done({status:'tts-timeout'})`을 실행하면 성공과 실패를 올바르게 구분할 것이라는 가정은 틀림.
- 재현: `tests/team11_audio_user_activation.test.cjs`의 `P0 independent QA: opt-in synthetic timeout...` 반례. 가짜 브라우저가 cancel 중 onend 동기 호출.
- RED SHA: `3b4f2826e0e0f9df43996067f7515025da71ed91`; CI [#40998155238](https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40998155238) FAILURE, 실제 `tts-played` vs 기대 `tts-timeout`.
- 근본 원인: `hangul-core.js` `synthesize()` 타임아웃에서 브라우저 취소 이벤트가 실패 판정보다 먼저 결과 Promise를 완료함.
- 실제 수정: `done({status:'tts-timeout'})`을 먼저 실행한 뒤 `speechSynthesis.cancel()`을 호출하고 브라우저 예외를 처리. 제품 SHA `ca6e5f2a0224f081345791f645581a895a2794a8`.
- GREEN: 동일 격리 브랜치 [#40998196056](https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40998196056) completed SUCCESS. 기존 음성 사용자 제스처/취소/보류 검사도 통과.
- 금기: `cancel()`이 비동기일 것이라고 가정하거나 `onend`를 무조건 재생 성공으로 계산하지 않는다. 사람 녹음의 발음 승인·실기기 청취·Render99 배포 성공으로 승격하지 않는다.
- 타 팀 교훈: 11/12팀의 모바일 오디오·선택형 TTS 경로는 종료 이벤트보다 먼저 실패/취소 상태를 확정하는 회귀검사를 재사용. 13팀 Jitsi 종료 콜백에도 적용 가능성은 있으나 **검증 전 적용 성공 아님**.
- 후속: 11팀 코드 인수, 15팀 최신 통합 SHA 교차 회귀, 12팀 463개 음성 경로/사람 청취 승인, 테스트99 SHA·SQLite 복구 확인 전 배포 금지.
