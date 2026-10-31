# PR #162 — 5분 GitHub 작업요청 감시 및 영속 워커 인계 실험

2026-10-31 중앙 총괄본부 P0. **Draft / main 미병합 / 운영 미기동**.
기존 #157 상태기계 파일럿의 READY 판정과 별도다. PR #156의 #102 477 tests/14 반례는 재실행하지 않는다.

## 읽기·변경 범위

- `.github/workflows/continuous-work-request.yml`: 5분 cron은 **기본 브랜치에 워크플로가 존재할 때만** 스케줄 대상이 된다. 현재 Draft PR에서는 예약 실행이 시작되지 않는다. GitHub는 5분 정시를 보장하지 않는다. `issues:write` 권한도 GitHub 설정·실제 run으로 확인해야 한다.
- `automation/continuous_dispatcher.py`: 전체 open issue 페이지(100개 단위) 순회, PR 제외, 동일 marker 열린 작업 1건만 유지. 2건 이상이면 BLOCKED. 60분 이상 미처리이면 STALE 실패로 경고하고 새 이슈 생성 금지. 403 권한 거절은 실패 처리, 제한 초과/5xx만 제한 재시도. POST 직전 2차 조회. `APPLY_QUEUE=true` 없으면 읽기 전용.
- `automation/test_continuous_dispatcher.py`: >100개, 정확히 100개, 페이지 상한, 권한 거절, 503/429 계열, 중복, 오래된 요청, 경쟁 상태 등을 검증한다.
- `automation/work_request_worker.py`: 외부 영속 디스크의 SQLite에 이슈를 멱등 수신하고 `BEGIN IMMEDIATE`로 단일 임대·heartbeat·기한 만료 복구·최대 3회 재시도·결과 보고를 기록하는 **로컬 인계 계약**. 코드 자체가 ChatGPT를 호출하거나 GitHub 이슈를 닫거나 READY를 승인하지 않는다.
- `automation/test_work_request_worker.py`: 재시작 보존, 이중 임대 거절, 만료 복구, 3회 실패 BLOCKED, 다른 worker의 완료 거절 등 반례.
- `.github/workflows/event-driven-ready-gate.yml`: PR #162 변경 경로를 트리거하고 위 두 신규 테스트 모듈을 실행하도록 격리 브랜치에서만 변경.

## 독립 QA 및 최종 READY 차단

1. PR #162 정확 HEAD에서 중앙 CI **실제 Actions run ID와 원시 로그** 확보. CI가 시작하지 않았으면 `CI_PENDING`, 테스트 코드를 작성한 사실을 `CI_PASS`로 보고하지 않는다.
2. 15팀은 중앙 정확 SHA로부터 QA-only 브랜치 생성, 정상/오류/경계값 반례 추가, 별도 실제 자동화 run ID와 Actions 원시 로그로 QA_PASS/FAIL. 같은 GitHub 계정은 별도 GitHub APPROVED가 아니다.
3. 테스트가 통과해도 **GitHub issue 생성 ≠ ChatGPT 개발자 기동**. 현재 외부 ChatGPT API 작업자, 인증된 호출 경로, 실제 영속 디스크 호스팅, end-to-end ack, 복구 후 중복 외부 부작용, 비용 제한, 24시간 실증은 없다.
4. 외부 워커 연결 전 필수: 별도 비밀키·서명/권한, 영속 볼륨·백업 복원, worker의 issue/lease 소유권 검사, 작업 SHA와 브랜치 계보 검증, 실행별 idempotency key, 비용·호출 상한, 독립 15팀 QA, 운영과 분리된 테스트 환경.
5. SQLite 임대는 **한 DB를 공유하는 worker들 사이에서만** 중복 claim을 막는다. GitHub POST는 트랜잭션이 아니며 두 독립 watchdog 간 완전한 exactly-once를 보장하지 않는다. ChatGPT 작업 호출 및 외부 부작용의 exactly-once도 보장하지 않는다.
6. 실제 워커 연결/호스팅·TEST99 배포/DB/결제/송금은 이 PR에서 수행하지 않는다. main 병합·운영 변경 금지. 완료 판정 `INTERNAL_READY=0` 유지.

## 운영자의 다음 순서

중앙: PR #162의 CI 실제 기동 확인·실패 로그 수정 → 15팀 독립 QA 요청·수신 → 외부 인증 워커·영속 디스크의 격리 E2E 설계/구현 → 재시작/중복/권한/비용/이슈 닫힘 검증. 15팀: 정확 SHA 반례 QA. 무인개발팀: 중앙 쓰기·CI·환경 차단 시에만 지원. #103 PR #161의 기존 QA 요청은 별도로 추적한다.
