# 한글쉽지 6팀 1시간 실증 감사 — 2026-10-29 16:32 KST

## 범위·기준
시작 기준: CODE_VERIFIED 13/160, 상세 계약 16/160, READY 0, OWNER_APPROVED 0, 신규 6팀 AI 호출 0.
직접 조회: 6팀 전수 지시, AGI 지시, 재귀형 HQ 조직, 테스트99 수락 지시, 3개 예약 작업 최신 저장 보고, 4개 Actions 실행의 실제 jobs 및 job logs, automation/task-evidence.json, automation/hq_semantic_contract_paths.json, 원본 160개 계약 표, 각 팀 bot SHA/diff.
독립 실행의 실제 근거는 원본 CI #40797947894의 team12 develop job 로그 `Round 1: committed=0, calls=0`; supervisor도 신규 개발 없음. 본 실험 시점 이후 추가 6팀 bot 실행이 없다는 판단은 최신 자동화 보고와 직접 조회한 해당 job 범위에 한정한다.

## 팀별 1시간 자율 개발 판정
|팀|과제 선택/기존 bot|이번 시간 신규 실제 AI 호출·diff·독립 QA·승계|판정|
|---|---|---|---|
|11|과거 #56 bot f7b52ebf, #11 preflight HQ 직접 수정|신규 팀 AI 0 확인, 팀 내부 하위 역할 호출·연속 승계 없음|FAIL|
|12|과거 #49 bot a61974ef, 코드 검증 #49|마지막 develop job `committed=0,calls=0`; 새 하위 실행 없음|FAIL|
|13|과거 #47 bot cbf75b2c는 소유권 오류로 거절; #22 403/200 회귀 미해결|새 개발/복구·QA·승계 미입증|FAIL|
|14|과거 #109 bot e75d948d|신규 호출·반례 구현·독립 검증/승계 없음|FAIL|
|15|과거 #8 bot 2760c9c7, HQ 별도 동적 READY QA 32 PASS|신규 팀 AI 하위 호출 없음; HQ 직접 작업은 팀 실적으로 불인정|FAIL|
|16|과거 #55 bot ccac78a7, 가상 IR 반려 상태|신규 팀 AI·재심사·전이 평가 없음|FAIL|

**전이/AGI 판정:** 자동 CI는 A=PASS. 팀별 실제 신규 AI 개발 B=FAIL. 2팀 이상 3회 연속 자율 개발·독립 QA·승계 C=FAIL. 새 과제 전이 실험 D=UNKNOWN(실행 증거 없음). AGI 달성 근거 없음. 조직 정의와 총괄의 수동 코드 수정은 여섯 팀의 자율 하위 AI 호출이 아니다.

## 실제 Actions 교차 검증
- #40797947894 develop(12) job 123198868346: 2026-10-29 10:02 KST `Round 1: committed=0, calls=0`; supervise job 123198973460 SUCCESS는 신규 제품 개발 아님.
- #40830582694 preflight-regression job 123303626531 SUCCESS, HQ #11 안전장치 검증, 팀11 모델 호출 아님.
- #40831933689 independent-dynamic-ready-review job 123307915191 SUCCESS, 32개 회귀 검사, 신규 READY/AI 개발 없음.
- #40832650710 test99-acceptance job 123310162702 SUCCESS, 11개 테스트 및 읽기 전용 서버 탐색. 실제 수락 결과는 `BLOCKED`임. 라이브 healthz 200, mode=test, scope=isolated-staging, 비인증 홈 401. 라이브 source SHA256 e9d13683... vs 후보 ed0101f5..., verified_deploy_sha=null, authenticated/mobile browser=false.
- 마지막 각 팀 bot SHA 직접 fetch_commit: 11 f7b52ebf, 12 a61974ef, 13 cbf75b2c, 14 e75d948d, 15 2760c9c7, 16 ccac78a7. 모두 이번 1시간의 새 bot SHA 아님.

## 160개 증거 원장·구조적 원인
- `automation/task-evidence.json`: CODE_VERIFIED 13개, COMPLETE 0개, #22/#47 BLOCKED. CODE_VERIFIED 13/160=8.125%; 대표 승인 0/160.
- `automation/hq_semantic_contract_paths.json`: 파일/테스트 경로가 등록된 항목 24개(시작 시 22개). **24는 상세 계약/READY/기능 완료 수가 아님.** READY 0.
- 원본 `docs/HQ_160_DEVELOPMENT_CONTRACTS_20261029.md`에는 6팀 전수 지시와 서로 다른 **49개 소유권 표기**가 있었다: #1–10은 11·13, #31–40은 13, #81–100은 14 우선, #141–142/#144–150은 13 우선 표기. 실제 전수 지시의 단일 책임팀은 각각 15,11,13,16. 이 모순은 자율 작업 배정과 독립 QA 충돌의 실질적 위험이다.
- 자동 개발 runner는 단일 Python 파일과 엄격한 READY gate에 제한됨. 검증된 READY 0이어서 실제 AI 호출이 생기지 않음. 원본 test99는 기존 Render 무료 임시 SQLite 데이터 보호 미확인으로 안전한 자동 배포 불가.

## 이번 감사에서 직접 수행한 코드/검증 조치
- 격리 브랜치 `audit/hq-one-hour-ownership-20261029` 생성, 원본 계약표 49개 소유권 표기를 canonical 단일 책임팀으로 교정. 지원팀은 지원으로 남김.
- `automation/test_hq_contract_owner_consistency.py` 신규 추가: 160개 누락/중복/담당팀 불일치 차단 및 오류 반례 3개.
- `.github/workflows/hq-owner-consistency.yml` 신규 추가: PR 대상 Python 독립 검증 워크플로.
- GitHub 원본 160행을 읽은 JS 교차 검산: **160개 고유 ID, 누락 0, 잘못된 1차 소유팀 0**, 팀별 30/30/30/40/20/10. Python CI 실행/성공은 아직 미확인. **수정은 HQ 감사 직접 변경이며 팀별 bot 실적으로 계산 금지.**
- Draft PR #27. 15팀 독립 의미 검증 및 CI 확인 전 HQ 브랜치 병합 금지.

## 테스트99·대표 확인
- 운영 홈페이지: https://anigio2705-dev.github.io/hangeul-swipji/
- 테스트99: https://hangeul-swipji99-test.onrender.com/
- 이번 변경은 계약 소유권 및 회귀 테스트만이며 테스트99에 화면 변화 없음. 최신 후보 코드 배포 SHA 미확인, 기존 과거 배포 기록 0aa0092/ad5757d는 현재 버전 증명 아님. 예약·모의 결제 데이터가 임시 SQLite에 존재할 수 있으므로 백업/격리/배포 경로 확인 전 재배포 금지. 대표 승인 0.

## 다음 실행에 필요한 구체적 조치
1. PR #27의 실제 Python CI·15팀 독립 검토를 확인해 안전하게 통합하고 소유권 모순 재발 방지.
2. 기존 #11 preflight PR #24, READY 감독 PR #25, 테스트99 gate PR #26을 독립 의미/보안 검토 후 순차 통합(충돌 조정).
3. 각 팀은 책임 번호 중 실제 소스·검사 경로를 찾아 15팀 검증을 거쳐 최소 1개 READY 후보를 공급. 신규 하위 AI 호출/수정 diff/실패 복구/다음 번호를 job별로 기록.
4. 11/13팀은 Render 현재 배포 SHA·서비스 설정·임시 DB 보호를 확인, 15팀은 PC/모바일 실제 E2E와 배포 SHA를 검증한 뒤 **테스트99만** 배포. 운영/main/운영DB/실결제/대외 제출 금지.

이 감사는 6팀 자율 개발 성공이 아니라, **자율 실행 정체를 확인하고 소유권 충돌 49건의 재발 방지 변경을 격리 PR로 제안한 결과**다.
