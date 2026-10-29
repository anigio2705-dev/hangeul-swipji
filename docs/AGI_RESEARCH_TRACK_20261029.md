# AGI 구현 연구 트랙 — 실행 계획 및 실험 기록
기준일: 2026-10-29
상태: 연구 설계 및 자동 운영 연결 준비. **AGI 구현·성능 향상 검증 전.**

## 목표와 분리
최종 목표는 AGI 구현. 한글쉽지 160개 개발 계약은 장기 자율 수행의 첫 실험 환경으로 사용한다. 160개 코드 검증/최종 승인 지표와 AGI 연구 성과를 합산하지 않는다.

## 첫 실험: 장기 자율 개발의 일반화
- 가설 H1: AI 팀이 단순 예약/CI 반복을 넘어, 원문 요구사항에 맞는 과제를 독립 선택하고 개발·수정·검증·다음 과제까지 3회 이상 이어갈 수 있다.
- 가설 H2: 이전 실패에서 추출한 회귀 검사를 적용하면 같은 오류 재발률이 감소한다.
- 가설 H3: 한글쉽지와 구조가 다른 격리된 테스트 프로젝트에서도 같은 개발 제어 방법론이 통한다.
- 가설 H4: 세션을 넘어 계약, 의사결정, 실패 원인, 후속 계획을 근거와 함께 유지한다.

## 평가 단위 및 기록 스키마
각 사이클은 다음 필드를 반드시 기록한다.
`run_id, started_at, agent_team, task_id, task_source, choice_reason, baseline_commit, ai_call_evidence, code_diff, test_before, failure_reason, correction_commit, test_after, independent_qa, next_task_dispatch, human_intervention, elapsed_time, cost_estimate, safety_boundary`.

## 통과 기준
- 자동화 실행(A), 실제 AI 코드 변경(B), 무인 연속 실행(C)을 별도 PASS/FAIL/UNKNOWN으로 판정.
- C 통과의 최소 내부 기준: 인간의 새 지시 없이 연속 3개 개발-독립검증-차기배정 사이클, 서로 다른 팀 2개 이상에서 실제 AI 호출과 코드 변경 확인.
- 일반화는 처음 보는 과제와 별도 테스트 저장소에서 평가. 원래 작업을 반복한 결과만으로 일반화 통과 금지.
- 오류 복구는 실패 로그, 원인 진단, 수정 diff, 동일 회귀검사의 재통과가 모두 있어야 인정.
- 안전: 운영 배포/main/운영 DB/실결제/실제 정부지원 제출/대외 접촉은 명시 승인 없이 금지.

## 첫 실행 백로그
1. 기존 CI/커밋/작업 큐에서 실험 베이스라인을 수집하고 A/B/C 근거 표 작성.
2. READY=1(#56)이 신규 AI 개발 호출 0건으로 끝난 원인 분석; 중복 작업 회피와 큐 기아를 분리.
3. 검증 가능한 신규 READY 과제 공급과 독립 QA를 통해 첫 연속 사이클 기록.
4. 실패 원인을 재현 가능한 테스트로 만들고 동일 유형 재발률을 추적.
5. 기존 코드에 맞춘 테스트가 아닌 새로운 과제·다른 환경의 홀드아웃 평가를 설계.
6. 매 실행 시 실험 근거와 미입증 사항을 기록하고 AGI 달성으로 표현하지 않는다.

## 현재 베이스라인 (2026-10-29 12:28 KST 보고 기준)
160개 계약, 코드 검증 9/160, 경로 상세화 11/160, READY 1, 최종 승인 0/160. 6팀 연속 AI 개발은 미입증. 이 수치는 이후 자동 실행 시 실제 근거로 갱신한다.

## 2026-10-29 13:04 KST — H1/H2 첫 실측 실험 (AGI 달성 주장 금지)
- 원본 160개 계약과 실제 ledger 재조회: CODE_VERIFIED 11/160 (#10,#41,#43,#44,#49,#52,#54,#55,#56,#59,#109), 최종 승인 0/160. 13개 과제의 의미 계약 경로를 등록했고, #45는 CANDIDATE로 유지. READY 0.
- **H1(A 자동화 실행): PASS** — #44 CI 40813528164, #56 CI 40813120338, 160개 큐 CI 40813595826의 실제 성공 기록 확인.
- **H1(B AI 개발): 이 실행에서 FAIL/미입증** — 마지막 확인된 6팀 개발 작업은 AI 호출 0회·신규 봇 커밋 0건. HQ 직접 코드/테스트 수정과 AI 팀의 신규 커밋은 별도 계산.
- **H1(C 무인 연속 실행): FAIL/미입증** — 3개 연속 자율 개발-독립검증-다음 배정 및 서로 다른 팀 2곳 이상의 신규 AI 개발 기록이 없다.
- **H2 첫 실험:** 실제 7개 학습 HTML의 350단원, 퀴즈 1,758개를 원본 데이터에서 추출해 보기 중복·정답 인덱스·해설 필드 존재를 검사했다. 보기 중복 0, 정답 인덱스 오류 0, 문항별 명시적 해설 0/1,758. 정답 의미의 교육적 유일성은 별도 검증이 필요하며, #45 전체를 완료했다고 주장하지 않는다.
- **재현 반례:** 중복 보기, 범위 밖 정답 인덱스, 누락 단원 입력을 검증기가 거부하도록 독립 부정 테스트 3종을 작성했다. 자동 검사 파일 automation/verify_task45_quiz_integrity.cjs (코드 커밋 e307e597).
- **CI 실패→원인→수정:** 첫 실행 40815779317에서 퀴즈 데이터 검사는 PASS였지만, 워크플로 YAML의 평문 #45가 주석으로 해석되어 마지막 요약 명령이 잘려 job이 FAIL. 해당 명령을 YAML block scalar로 수정(커밋 69b50e42). 새 CI 최종 결과를 확인하기 전에는 성공으로 보고하지 않는다.
- **다음 실험:** #45의 해설 0건을 실제 콘텐츠/화면 수락 조건에 연결하고, 점수·재도전 동적 검사 및 교육적 정답 의미 검증을 추가한다. 자동 READY 공급과 개발팀 AI 호출의 폐회로는 별도로 복구한다.
- **참고 방법론:** OpenAI Agent Improvement Loop(실제 실행 traces→피드백→재현 가능한 eval→개선→재검증). 예전 Codex CI autofix 예시는 archived이며 비밀키·쓰기권한이 같은 job에 있는 설계를 그대로 복사하지 않는다. 최소 권한·격리·독립 검증을 유지한다.

## 13:08 KST — H2 후속 회귀 실험
실제 7개 교육 스크립트의 전체 오답 점수 0/N과 재도전 UI 복원을 실행 검사로 추가했다. 수정 커밋 8526fefc, 독립 CI 40815975914 SUCCESS. 1758개 문항 데이터 무결성 CI 40815818683 SUCCESS. 그러나 해설 0/1758과 교육적 정답 의미 검증이 남아 #45 CANDIDATE를 유지한다. 이 성과는 AGI 범용성 증명이 아니라 테스트 자동화와 실패 학습의 실험 증거다.

## 실험 기록 — 2026-10-29 14:06 KST, #46 모바일 읽기 회귀
- 실험 유형: **H2 실패→원인→수정→동일 평가 재검증**. 범용지능 구현 실험이나 신규 AI bot 자율 호출은 아님.
- 관찰: 375px 모바일에서 레벨을 선택하면 사이드바가 숨겨져 다른 레벨로 재선택할 수 없는 실제 UI 결함 발견.
- 변경: `reading.html`의 레벨 변경 버튼 `09f2ffcfcbf0a6928614577b4c0a2bb51b37482f`; 실제 Chromium 600개 구조+375px 상호작용 평가 `scripts/browser-audit-reading-600.cjs` 커밋 `bcde9f20273a5588ff19279330a21a2c0b8aa016`.
- 첫 평가 실패: GitHub Actions `40821383705`, Playwright 1.58.2가 기본 ubuntu-latest(26.04)의 브라우저 설치를 지원하지 않음. 기능 코드 오류와 테스트 환경 오류를 분리.
- 수정: CI 실행 환경을 ubuntu-24.04로 고정, `47d484fd5b006d2378b127e0f31539f703509180`.
- 독립 결과: `40821422787` SUCCESS (정확한 SHA). Chromium에서 읽기 600개 구조 검사 PASS, 375px 레벨10→15 이동·40번째 책·오답 0/3→정답 3/3·근거 3개·로컬 진도 재접속·가로 넘침 없음 PASS.
- AGI 증거 A: 자동 실행/평가 PASS. B: **이번 수정은 총괄 직접 수행, 6팀 신규 AI 봇 호출·커밋 0**. C: 여러 팀의 무인 연속 자율 개발 미입증. 새로운 도메인으로의 범용 전이 미검증.
- 연구 해석: 실패와 수정 및 재검증을 구조화해 보존한 것은 재현 가능한 자기교정 워크플로 증거이나, 모델의 지속 학습·AGI 달성 증거는 아니다.
- 한계: 실서비스·실제 휴대폰 미검증, 전체 600개 모바일 흐름 미검증, 교육적 정답 유일성 미검증, #46 CANDIDATE 유지, 최종 승인 0/160.

## 실험 기록 — 2026-10-29 14:58 KST, H1 자동 과제 승계 병목의 반례
- **가설:** 실제 READY 과제가 고정된 CURATED_TARGETS 밖에 있으면 기존 개발 제어기는 새 작업을 배정하지 못한다. 독립 READY 경로 검증을 기존 next_assignment에 연결하면 고정 목록 밖의 과제를 안전하게 배정할 수 있다.
- **실제 변경:** `automation/hq_160_task_cycle.py` 커밋 `3d205074`; `automation/test_hq_160_task_cycle.py` 커밋 `2b220a91`; 별도 CI `hq-ready-dispatch-regression.yml` 커밋 `fa3d49f3`.
- **실험 설계:** 신규 READY #45를 임시 독립 테스트 환경에서 구성해 올바른 12팀 배정과 13팀 배정 거부를 비교. 독립 15팀 PASS 누락, 잘못된 경로, 중복 파일 충돌, 진행 중 중복 호출, 재시도 한도, 다중 소스 패치를 거부하도록 반례를 추가했다. 이는 **가상 READY 검증**이지 실제 #45 READY 승격이 아니다.
- **관측:** GitHub에 코드·테스트·워크플로 저장 확인. **CI 실행 번호와 최종 성공 여부는 이번 실행에서 조회되지 않아 미확인.** 결과가 PASS로 확인되기 전 실험 성공으로 집계 금지.
- **실제 운영 기준선:** 코드 검증 13/160, 최종 승인 0/160, 실제 READY 0, 6팀 신규 AI 호출·봇 커밋 0. 이번 수정은 HQ 직접 수행한 컨트롤러 개선이며 AGI 능력 전이 증거가 아니다.
- **다음 검증:** 정확한 커밋 CI 통과 후 실제 독립 검증된 READY 1개 공급→실제 팀 AI 호출·diff·실패 복구·다음 과제 자동 승계 증거를 수집한다. 16팀 모의 심사와 160개 제품 완료율은 별도 집계한다.

## 2026-10-29 15:30 KST — H1 실행기 단절의 실제 수정과 반례 평가
- **발견한 원인:** `automation/hq_160_task_cycle.py`에 동적 READY 선택 함수가 추가됐어도 실제 AI 작업 실행기 `automation/hq_six_developers.py`는 `TASKS[team]` 고정 목록만 순회했다. 즉 선택기 테스트 PASS와 실제 6팀 작업 배정은 다른 경로였다.
- **수정:** 실행기가 `next_assignment`의 독립 검토된 READY 후보를 우선 소비하도록 연결. Python 단일 파일+실행 가능한 unittest 검증만 허용하며 HTML/JS 등 지원하지 않는 변경은 `ready_unsupported_target`으로 보고해 무단 변경을 차단. 해당 작업별 테스트를 변경 전후에 수행하고 0개 테스트 성공을 거절. 격리 워크플로에 신뢰된 `hq_traffic_lights.py` 복사를 추가.
- **코드/테스트 커밋:** `f12e559d`, `28ac5be1`, `425d48a0`, `e174df4e`, `0ffbd430`, `034106ef`. 실제 독립 CI `40829591769` SUCCESS (정확한 테스트 커밋 `0ffbd430`), runner READY 연결 및 0-tests 반례가 통과했다.
- **실험 A:** GitHub CI 및 안전한 정적/합성 READY 배정 검증 PASS. **실험 B:** 실제 신규 AI 호출 및 신규 bot 코드 커밋 확인되지 않음. **실험 C:** 3회 연속 자율 개발/2팀 이상 참여 미입증. 합성 READY 평가를 실제 봇 자율 개발로 계산하지 않는다.
- **잔여 병목:** 실제 READY 0개, 160개 중 13개 코드 검증, 최종 승인 0개. 등록된 후보 중 #45/#46/#51은 여러 파일/JS·HTML 범위를 포함하므로 Python-only runner에 잘못 투입하지 않는다. 안전한 실제 단일 Python READY 과제와 팀별 테스트가 필요하다.
- **일반화 해석:** 큐 선택 로직이 실행기로 이어지지 않는 '선택-실행 단절'을 재현 가능한 테스트로 막은 것은 하네스 개선 증거다. 모델의 AGI 능력이나 새 도메인 일반화 증거는 아니다.

## 2026-10-29 15:57+ KST — H2 증거 일반화 실험: 개발 코드와 실제 테스트99 배포 구분
- **가설:** 저장소의 성공 CI와 실제 배포된 코드가 다른데도 같은 완료로 보고하는 오류를, 배포 SHA 및 원본 파일 해시의 독립 검증으로 차단할 수 있다. 기존 학습/예약의 의미 검증과 달리 배포 증거라는 새 유형에 같은 실패-반례-수정 규칙을 적용한다.
- **실제 조사:** `deploy/STAGING99.md`, `audit/staging99-deployment.json`, `docs/audit/team11-99-gap.md`를 교차 읽어 테스트99 실제 주소 `https://hangeul-swipji99-test.onrender.com/`와 2026-10-27 문서상 배포 `ad5757d`, 자동배포 Off, Free 임시 SQLite 소실 위험을 확인. 현재 Render SHA는 미확인이다.
- **실제 변경:** `phase3/staging_server.py`에 형식 검증된 `deployedCommit`만 노출(코드 `f94a4503`); `phase3/test_staging.py`에 정상 40자리와 빈/39자리/비16진수 입력의 부정 테스트 추가(`b9018e65`). `.github/workflows/hq-test99-provenance.yml`(`b5f1382e`)에 격리 서버 로컬 회귀와 읽기 전용 HTTPS 실서버/정확한 SHA 비교를 분리했다. 테스트99에 배포하지 않았다.
- **A 예약 실행/CI:** GitHub 워크플로 정의를 저장했지만 이 기록 시점 신규 CI 실행 번호·성공 여부는 미확인. **B 실제 AI 개발:** 여섯 팀 신규 모델 호출·봇 커밋 0으로 확인된 최신 감사 결과 유지. **C 연속 자율 개발:** 미입증.
- **판정:** 새 도메인에 동일 증거 평가 패턴을 적용한 총괄 직접 코드 변경이며 AGI 일반화 능력의 입증이 아니다. 테스트99 실제 HTTP/브라우저 검증과 15팀 독립 검증 후에만 수락 후보로 이동한다. 160개 코드 검증 13/160, 최종 승인 0/160으로 별도 유지.

## 2026-10-29 17:55~18:00 KST — H2 holdout: green CI is not representative acceptance
- **New failure class:** `automation/hq_160_task_cycle.py::make_report` counted a checked, CI-shaped `complete` record as final without any explicit representative approval for ordinary tasks such as #9. This is an evidence/approval semantics defect, not an AGI capability proof.
- **RED reproduced:** isolated branch `automation/hq2-owner-approval-20261029-1755`, synthetic tests `automation/test_hq_owner_approval_gate.py`, GitHub Actions [#40845856685](https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40845856685) FAILURE (3 of 5 checks failed as expected).
- **Correction:** `make_report.is_final` now requires both `representative_approval is True` and a nonempty `representative_approval_evidence` for **all 160 items**, preserving additional external and business gates. Code SHA `05bf8b2b`, legacy synthetic fixture update `cfec3436`.
- **GREEN independently re-run:** [#40845898003](https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40845898003) SUCCESS at exact SHA `cfec343641eae8947c6a65ef942a1e48b81b0a0e`; 5 new + 13 existing tests PASS. Draft stacked PR [#31](https://github.com/anigio2705-dev/hangeul-swipji/pull/31), unmerged.
- **Evidence limitation:** approval strings are claims and require independent 15-team verification against a real representative decision. The tests use fake approval records; **no actual task approved**. This is HQ-authored code, **six-team bot calls 0**. A (automated CI) PASS, B (team autonomous coding) NOT PROVEN, C (three autonomous cycles) NOT PROVEN, D (general AGI transfer) NOT PROVEN.
- **160 baseline:** isolated evidence ledger CODE_VERIFIED 13/160, mapped paths 25/160 including pending #9, READY 0, final representative approval 0/160. No test99 deployment; current live SHA unknown; database-preservation guard remains active. This eval does not increase product completion.
