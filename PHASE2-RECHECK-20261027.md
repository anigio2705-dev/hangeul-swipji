# 한글쉽지 2차 추가 수정·재검증 보고

판정: **코드 수정·자동 검사는 통과했으나, 2차 교육 서비스 전체 완료는 아님.** 필수 사람 녹음 359개와 교사 청취 승인이 남아 있다. 자동 해독·브라우저 재생 종료를 발음 정확성 승인으로 간주하지 않는다.

## 이어받은 기준과 실제 커밋

이전 `4b3f57c`, `2e5bb32`와 main을 확인한 뒤 이어서 작업했다. 실행 중인 이전 검사·수정 프로세스가 없어 중복 작업을 재시작하지 않았다. 기존 보고서는 이력으로 보존했다. 이 작업은 main만 조건부 fast-forward로 갱신했으며 `phase3/global-teaching-platform-20261026` 브랜치에 쓰기·병합하지 않았다.

| 커밋 | 실제 변경 |
|---|---|
| `3eaec8576d15866a2a78051c082cdee9093281ba` | 발음 실패·중단 처리, 듣기 완료 조건, 사람 녹음 후보 10개 보존 |
| `b95ec8bffc6a84b3b7c655a6e55e558aff2148db` | 읽기 대체 이야기·추론 문제, 내장 언어 처리, 음성 목록 JSON 본문 시간 제한 |
| `b004ca963ff2c649726d386115a8e7f7780ebb1d` | 남은 사람 녹음 후보 6개, 어휘 도움말, 언어 스크립트 캐시 갱신 |
| `4b6e7923c6fa1e0de2b0b4f3e2df133e9870f856` | 조사 문항 2개·읽기 주제 범위 수정, 재검토 근거·배포 검사 스크립트 |

마지막 코드 커밋의 [2차 검사](https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40403980066)와 [Pages 배포](https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40403979745)는 성공했다. 이 보고서와 함께 반영하는 검수표의 문구 수정은 ‘재생 가능’을 ‘자동 해독 검사 통과 · 실제 청취 미검증’으로 명확히 하는 변경이다.

## 발견·수정 사항과 재비판

서로 다른 결함 유형 6종을 보완했다. 아래 항목의 적용 수와 원인 수를 혼동하지 않는다.

| 문제 | 실제 수정·재검사 |
|---|---|
| 듣기 버튼을 누르기만 하면 완료될 수 있음 | 정상 재생 종료 결과를 받은 뒤 정답을 선택해야 듣기 완료. 보류·누락·실패·중단은 완료 불가 |
| 음성 요청·재생이 멈추거나 거절될 때 처리 불완전 | 목록 응답과 JSON 본문, 재생에 15초 제한. HTTP/미디어 오류·시작 거절·중단 구분. 합성 음성 대체 없음 |
| 내장 영어와 외부 번역의 충돌 | 직접 `?lang=en` 진입·한/영 선택에 내장 번역 사용. 외부 언어 선택이 한국어/영어 전용 핸들러를 실행해 오류 내지 않도록 분기 |
| 조사 정답의 의미상 복수 가능성: 개별 문항 2개 | 초급1 3단원 ‘책___ 있어요’는 주격 조사, 4단원 ‘밥___ 먹어요’는 목적격 조사라고 한·영 질문에 명시. 기존 선택지·정답·문항 수 보존 |
| 읽기 주제 범위 모호: 공통 템플릿 1개, 600항목에 적용 | 실제 화면에서 아침 이야기 후반의 버스 사건 때문에 ‘버스 정류장’도 해석 가능한 문제 발견. 첫 세 문장의 주제를 묻도록 범위 명시 |
| 주제별 두 과제의 본론 반복: 20쌍 | 두 번째 과제용 이야기 20개·한영 문장쌍 280개 연결. 상위 6레벨에 추론 문제 60개(10개 템플릿) 배치 |

Self-Refine 후 Kill Critic 재검토에서 ‘파일 해독 성공=발음 정확’이라는 해석, JSON 본문 무한 대기, 주제 문제의 버스 선택지, 조사 ‘는’의 자연스러움을 다시 문제 삼아 수정했다. 통과 결과만으로 전체 완료를 선언하는 것을 차단했다.

## 교육 내용과 읽기: 자동 검사와 AI 검토의 구분

- 350단원, 수업 퀴즈 1,758개, 예문 1,050개, 어휘쌍 2,112개 보존. 홈페이지 `index.html`은 기존 기준과 동일하다.
- 이전 350단원 AI 교육 검토는 [기존 기록](audit/lesson-review.json)에 보존했다. 이번에는 모든 단원의 구조·한영 쌍·정답 대응·기계적 한글 조합을 재검사했다. 단원별 해시와 변경 필드는 [재검토 기록](audit/recheck-review.json)에 있다. 일반 대응 검사 밖의 67문항을 추가로 읽어 위 조사 문제 2개를 고쳤다. 이번 검사를 새 교사 전수 검수라고 부르지 않는다.
- 1,513문항은 원문 대응, 178문항은 한글 조합·분해 규칙으로 자동 대조한다. 나머지 67문항의 의미 검토는 AI 검토이며 자동 증명이 아니다.
- 읽기 600항목·1,800문항·600개 기존 원문과 번역 보존 검사 통과. 새 이야기 20개는 사건·시간 순서·문법·한영 문장 대응을 읽어 검토했고, 추론 10개 템플릿은 명시된 근거와 오답의 반대·과잉 주장 여부를 별도로 검토했다.
- 전체 동일 레벨 11,700쌍을 어절 3개 묶음 Jaccard로 비교했다. 0.65 이상 97쌍 → 0쌍. 전체 본문 정확 중복 0개. 이는 **의미적 독창성의 증명은 아니다**.
- 600개는 40개 이야기 계열의 단계별 변형이다. 인접 레벨 560쌍의 앞부분 반복은 남아 있다. 600개의 독립 이야기로 표시하지 않는다.
- 레벨1 평균 8.55어절·문장 최대 4어절 → 레벨15 평균 115.60어절·문장 최대 14어절. 어휘 표면형·문법 형태 지표를 레벨별로 기록했다. 조건·대조·인용·근거 표현을 점진적으로 늘렸지만 CEFR/TOPIK 난이도 교정이나 초보자 실험은 하지 않았다.
- [전체 자동 검사](audit/phase2-content.json), [유사성·문법 지표](audit/reading-similarity.json). 문자 그대로의 정답 근거 유일성은 의미상 모든 해석의 유일성을 보장하지 않는다.

## 발음: 41개 문제와 375개 누락의 정확한 재판정

기존 등록 62개 중 41개는 손상되어 해독할 수 없는 파일이 아니라, 출처·임시 분할 대응·음질/청취 검수 사유로 **일반 학습 화면에서 차단한 파일**이었다. 기존 62개 모두 해독 가능했다. 임의로 차단을 해제하지 않았다.

추가 사람 녹음 16개: 개·게·계·과·괴·그·데·뒤·뭐·수·시·채·후·또·때·씨. Commons 원본 메타데이터의 작성자 HappyMidnight와 CC BY-SA 4.0 조건을 확인하고 전체 원본을 MP3로 변환했다. 새 파일의 자르기·이어 붙이기·합성은 하지 않았다. 10개 이후 HTTP 429로 멈춘 내역을 보존했고, 이후 한 번 재시도해 남은 6개를 확보했다. 현재 이 후보군의 다운로드 대기 0개다.

| 구분 | 이전 | 현재 |
|---|---:|---:|
| 등록된 사람 녹음 파일 | 62 | 78 |
| 파일 해독 검사 통과 | 62 | 78 |
| 일반 화면 재생 허용 | 21 | 21 |
| 일반 화면 재생 보류 | 41 | 57 |
| 필수 고유 발음 대상 | 418 | 418 |
| 필수 대상 중 파일 있음 | 43 | 59 |
| 필수 대상 중 파일 없음 | 375 | 359 |
| 필수 대상 중 일반 화면 재생 허용 | 19 | 19 |
| 실제 청취 승인 | 0 | 0 |

자음 이름 19개: 파일14·누락5·일반 재생0. 모음21개: 파일17·누락4·일반 재생9. 음절399개: 파일45·누락354·일반 재생19. 모음 음절은 음절판에도 포함되므로 그룹 수를 단순 합산하면 중복된다. 입문·7일 과정까지 넓힌 전체 463개 대상에서는 파일78·누락385다.

누락 자음 이름: 쌍기역·쌍디귿·쌍비읍·쌍시옷·쌍지읒. 누락 모음: 얘·워·웨·의. 전체 항목은 [청취 대기표](audit/audio-listening-queue.csv)에 있다.

자동 신호 경고 6개: 애(끝 여백), 개(앞뒤 무음), 게·과(앞 무음), 시(진폭·끝 여백), 채(진폭). 모두 보류 상태다. 경고는 오류 확정도 정확성 승인도 아니다. 청취 없이 여백을 임의로 잘라 경고를 없애지 않았다.

한글 화면은 사람 녹음만 사용하며 과거 합성 후보 26개는 제외한다. 수업·읽기의 기기 TTS는 별도로 표시한다. [출처·이용 조건](hangul-audio-credits.html), [파일·대상 검사](hangul-audio-audit.json), [확보 기록](audit/audio-acquisition.json).

## PC·모바일 및 배포 검증

마지막 코드 커밋 기준 Chromium에서 다음을 통과했다. 모바일은 390×844 에뮬레이션이며 실물 Android/iPhone 검증이 아니다.

- PC1440×900·모바일390×844 각각 12페이지 표시·가로 넘침·JS 예외 검사: 총24개 화면 통과.
- 수업 이동, 미응답 퀴즈 완료 차단, 정답 완료·재접속 진도 유지, 읽기 이동·번역 표시·추론·채점, 한영 URL 진입·전환 통과.
- 입문 보류 음성의 듣기 완료 차단, 정상 전체 재생+정답의 듣기 완료, 404 실패 처리 통과.
- 등록78개를 PC·모바일 각각 실제 브라우저 미디어로 재생해 종료 이벤트 확인: 78/78씩 통과. 검수용 직접 재생이며 보류57개의 일반 화면 차단은 유지한다. **자동 재생 종료는 교사의 실제 청취 검증이 아니다.**
- 읽기600개 브라우저 생성·퀴즈 구조, 350단원×한영2개=700뷰 문법·퀴즈 렌더링 통과.
- 고장 주입 검사: 누락·보류·비인간 출처 차단·시작 거절·동기 예외·미디어 오류·정지·목록 실패·JSON 본문 정지·시간 초과·중단, TTS 대체 없음.

실제 Pages 응답 파일 93개(음성78개 포함)의 HTTP 성공·SHA-256 일치를 확인했다. [배포 파일 검사](audit/live-delivery.json), [브라우저 결과](audit/browser-functional.json), [릴리스 근거](audit/recheck-release.json). `node scripts/audit-phase2-content.cjs --require-complete`는 녹음359개 누락과 청취 승인0개 때문에 의도대로 종료코드1을 낸다. 일반 소스 검사는 통과해도 완료 게이트는 통과하지 않는다.

## 미완료

필수 사람 녹음359개 확보/녹음, 보류57개 실제 청취·대응 승인(일부 재녹음 가능), 신호 경고6개 청취 판단, 전체 필수 발음418개에 대한 교사 승인, 실물 PC·Android·iPhone 환경과 실제 초보 학습자 시험, 외부 기계 번역 언어들의 의미 검수가 남아 있다. 사람이 수행해야 하는 작업을 코드나 승인 상태 조작으로 대체하지 않았다.

## 수정 파일

아래 목록은 이전 `2e5bb32` 이후 실제 변경 파일이며, 코드 변경과 검사·보고 산출물을 함께 포함한다.

- `.github/workflows/phase2-validation.yml`
- `PHASE2-RECHECK-20261027.md`
- `advanced1.html`
- `advanced2.html`
- `assets/hangul-audio/ac1c-20261027.mp3`
- `assets/hangul-audio/ac8c-20261027.mp3`
- `assets/hangul-audio/acc4-20261027.mp3`
- `assets/hangul-audio/acfc-20261027.mp3`
- `assets/hangul-audio/ad34-20261027.mp3`
- `assets/hangul-audio/adf8-20261027.mp3`
- `assets/hangul-audio/b370-20261027.mp3`
- `assets/hangul-audio/b4a4-20261027.mp3`
- `assets/hangul-audio/b54c-20261027.mp3`
- `assets/hangul-audio/b610-20261027.mp3`
- `assets/hangul-audio/bb50-20261027.mp3`
- `assets/hangul-audio/c218-20261027.mp3`
- `assets/hangul-audio/c2dc-20261027.mp3`
- `assets/hangul-audio/c528-20261027.mp3`
- `assets/hangul-audio/cc44-20261027.mp3`
- `assets/hangul-audio/d6c4-20261027.mp3`
- `audit/audio-acquisition.json`
- `audit/audio-listening-queue.csv`
- `audit/audio-source-search.json`
- `audit/browser-functional.json`
- `audit/live-delivery.json`
- `audit/phase2-content.json`
- `audit/reading-similarity.json`
- `audit/recheck-release.json`
- `audit/recheck-review.json`
- `beginner1.html`
- `beginner2.html`
- `hangul-audio-audit.json`
- `hangul-audio-credits.html`
- `hangul-audio-manifest.json`
- `hangul-audio-review.js`
- `hangul-basics.html`
- `hangul-core.js`
- `hangul-week.html`
- `intermediate1.html`
- `intermediate2.html`
- `intro.html`
- `reading-alternates.js`
- `reading.html`
- `scripts/audit-phase2-content.cjs`
- `scripts/audit-reading-similarity.cjs`
- `scripts/browser-functional-phase2.cjs`
- `scripts/check-audio-runtime.cjs`
- `scripts/curriculum-source.cjs`
- `scripts/find-human-audio-sources.py`
- `scripts/import-reviewed-audio-candidates.py`
- `scripts/refine-phase2-lessons.py`
- `scripts/verify-live-phase2.py`
- `site-language.js`
