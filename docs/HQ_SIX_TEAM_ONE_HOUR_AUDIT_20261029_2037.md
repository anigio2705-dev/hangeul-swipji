# 한글쉽지 여섯 팀 1시간 실증 감사 — 2026-10-29 20:41 KST

## 기준·검증 범위
- 기준선: 160계약, 코드 검증 13, 상세 증거 원장 16, READY 0, 대표 승인 0, 6팀 신규 호출 0.
- 직접 읽은 원문: `docs/HQ_SIX_TEAM_FULL_WORK_ORDERS_20261029.md`, `docs/HQ_SIX_TEAM_AGI_CAPABILITY_ORDERS_20261029.md`, `docs/HQ_RECURSIVE_SIX_TEAM_ORGANIZATION_20261029.md`, `docs/HQ_TEST99_MANDATORY_ACCEPTANCE_GATE_20261029.md`, `automation/task-evidence.json`, `automation/hq_semantic_contract_paths.json`, 워크플로·실제 러너.
- 자동화 최신 결과: 무인 개발 18:24, 6팀 정기 보고 19:52, HQ2 20:05 KST. 이 보고들은 중앙 수정과 실제 6팀 봇 작업을 분리한다.
- 마지막 **직접 조회 가능한** 여섯 팀 Actions 실행: [#40797947894](https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40797947894). 실제 job ID 123198868346 (develop 12), 123198973460 (supervise), 모두 성공 종료. develop 로그에는 `Round 1: committed=0, calls=0`. 여섯 팀 동시 실행 증거가 아니다.
- 최신 6팀 workflow run 전체 목록을 조회하는 GitHub connector action이 없어 **20:41 현재 새 6-job 실행의 부재까지 확정하지는 못한다**. 신규 호출 성공은 증거가 없으므로 미인정.

## 팀별 독립 개발 평가
| 팀 | 최근 확인된 봇 SHA / UTC | diff | 최근 한 시간 팀 자율 5단계 | 다음 과제 |
|---|---|---|---|---|
| 11 | `f7b52ebf` / 10-28 23:50 | `scripts/find-human-audio-sources.py`, #56 (12팀 소유) | FAIL | #11 |
| 12 | `a61974ef` / 10-29 01:00 | `phase3/learning.py`, #49 | FAIL | #45 |
| 13 | `cbf75b2c` / 10-29 00:35 | `phase3/learning.py`, #47 (12팀 소유) | FAIL | #22 |
| 14 | `e75d948d` / 10-28 23:44 | `phase3/team14_referral_store.py`, #109 | FAIL | #101 |
| 15 | `2760c9c7` / 10-29 00:07 | `scripts/team15_independent_gate.py`, #8 | FAIL | #153 |
| 16 | `ccac78a7` / 10-28 23:43 | `scripts/render-audio-credits.py`, #55 (12팀 소유) | FAIL | #143 |

판정 근거: 위 여섯 SHA의 GitHub commit과 changed-file diff를 각각 직접 확인했으나 모두 19:41~20:41 KST 밖의 과거 봇 커밋. 새 팀별 API 호출·하위 전문 AI 호출·실패 자기교정·다음 번호 자동 승계·홀드아웃 전이 평가를 입증할 증거가 없다. 과거 소유권이 맞지 않는 팀11/13/16 커밋은 정식 팀 소유 과제 완료로 세지 않는다. 중앙 HQ 수정은 팀 실적이 아니다. AGI 구현 또는 자율 3연속 사이클 달성으로 주장하지 않는다.

## 최신 160 증거 원장 직접 집계
- `automation/task-evidence.json`: **16개** 등록, `code_verified=13`, `blocked=2`, `unverified=1`, `complete=0`.
- `automation/hq_semantic_contract_paths.json`: 실제 소스·테스트 경로 계약 **24개** 등록, `CANDIDATE=11`, `BLOCKED=2`, `CODE_VERIFIED=11`, `READY=0`.
- 기준선 상세 계약 16 → 경로 등록 24: **+8개 경로 매핑**. 이는 신규 기능 8개 완료를 의미하지 않는다.
- #59는 중앙 원장 `code_verified`이나 무인개발 보고에서 발음 재생 회귀 미해결로 BLOCKED. 불일치 그대로 표시하며 최종 승인으로 인정하지 않는다.

## 지난 한 시간의 중앙 개선과 이번 감사의 실제 조치
- 19:51 KST 중앙 수정 `8389af63`: 실패 기록 시 `os` 미import, 이전 라운드 결과 재사용 위험을 수정. 독립 CI [#40860836255](https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40860836255) 성공. 다만 해당 수정은 별도 PR #35 초안으로, HQ 브랜치에 자동 반영된 증거는 없었다.
- 20:05 KST HQ2의 다국어 수정 `25b7ae02`, CI [#40862581841](https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40862581841) 성공. 이것은 중앙 직접 작업이며 팀16 AI 봇 성과가 아니다.
- **이번 감사의 실제 격리 브랜치 변경**: `cd828c78`에 `automation/test_hq_six_developers.py` 실패·중복결과 방지 회귀검사 추가. `e4ad3276`에 HQ 워크플로의 `os` import와 매 라운드 이전 결과 삭제를 적용하고, **승인된 격리 브랜치에서 READY registry가 변경될 때만** push로 여섯 job을 기동하는 제한된 트리거 추가. `35d3bd1a`에서 READY registry의 policy 문자열만 수정해 실제 push 진단을 요청. **READY 승격 0, API 호출 확인 0**. 변경 후 코드 정적 검사 6항목 통과 및 로컬 실패·오래된 결과 시뮬레이션 통과. 새 GitHub Actions run ID·6 job 성공·새 SHA의 독립 CI는 **미확인**이므로 PASS 주장 금지.
- 테스트용99 데이터 보호를 확인하지 못해 운영/테스트99 재배포 없음.

## 테스트99 수락·보호
- 운영: https://anigio2705-dev.github.io/hangeul-swipji/
- 테스트99: https://hangeul-swipji99-test.onrender.com/
- Render 서비스 `srv-dbg2fet9fdbs73cj08c0`; 과거 배포 `0aa0092`, **현재 실제 배포 SHA 미확인**.
- 대표 검수 클릭 순서: 테스트99 접속 → 인증 → 강의 개설 → 상대방 신청·수락 → 양측 연결 성립 → 화상수업 → 상태 추적. 이번 감사에서 브라우저 E2E 미실행.
- 임시 SQLite의 예약/모의 결제 데이터 보존·백업·격리 미확인. 재배포 금지. 대표 승인 **0/160**.

## 바로 다음 코드·검증 조치
1. GitHub Actions의 **이번 READY registry push 실행 ID와 6개 job 로그**를 확보한다. 단순 job 6개만으로 AI 호출 6개 성공이라고 세지 않는다.
2. 각 팀의 Python 단일 편집 파일·실제 독립 테스트·정확한 CI SHA를 확보하고 15팀 독립 검토 후 READY로 승격한다. 특히 팀15 #153 및 팀16 #143은 현재 등록/언어 파일과 Python-only 실행기 제약이 있으므로 새로운 실제 경로 또는 안전한 언어별 executor가 필요하다.
3. 실제 API 호출을 팀별로 구분해 6팀 병렬 개발·독립 검증·실패 재작업·다음 과제 승계를 증명한다.
4. 테스트99 영속 DB/백업/격리와 현재 SHA를 확인하기 전에는 재배포하지 않는다.

기존 자동화 일정·운영 홈페이지·main·실결제는 변경하지 않았다.
