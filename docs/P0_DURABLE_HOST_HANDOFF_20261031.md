# P0 / 무인개발팀 — 상시 호스트 준비 인계 (지원 전용)

기준: PR #162의 격리 워커; **main/운영/실결제/실지급 변경 금지**. 이 문서는 배치 완료 증거가 아니다. 실제 외부 호스트·인증된 Codex 호출·24시간 관측은 별도로 검증해야 한다. 중앙만 개발/INTERNAL_READY를 결정하고 15팀만 독립 QA를 수행한다.

## 발견한 연결 단절

PR #162의 `hangeul-ai-worker.service`는 AI runner만 시작한다. `work_request_worker.py`가 GitHub의 열린 작업 요청을 영속 SQLite로 ingest하지 않으면, runner는 빈 DB를 읽고 `IDLE`만 반복할 수 있다. GitHub Actions의 5분 schedule은 Draft PR에서 작동하지 않으며 실행되더라도 호스트 SQLite를 채우지 않는다.

## 제공 파일과 적용 조건

- `automation/deploy/hangeul-queue-sync.service` + `.timer`: 호스트에서 30초 간격으로 GitHub 이슈를 완전 조회하고 동일 영속 SQLite에 ingest/reconcile한다. sync 프로세스는 에이전트가 수정할 수 없는 root 소유 `/opt/hangeul-swipji-controller/automation` 코드 스냅샷에서 실행하며 별도 `/etc/hangeul-swipji/queue-sync.env`를 사용한다. **poll fallback일 뿐 GitHub 이벤트 즉시 실행이 아니다.** 오류 발생 시 systemd/journal에 실패가 남고 기존 큐를 성공으로 간주하지 않는다.
- `automation/deploy/host-preflight.sh`: 서비스 계정, 키 존재, 저장소, 영속 마운트, 격리 worktree, clean git, effective fetch/push URL, Codex 설치를 시작 전 검사. **에이전트가 수정할 수 없는 root 소유 호스트 경로에서만 실행**한다. 키 값은 출력하지 않는다.
- `automation/deploy/hangeul-ai-worker.service.d/10-host-guard.conf`: 중앙 소유의 기존 서비스 파일을 수정하지 않고 시작 전 fail-closed 검사, 격리 HOME 및 **AI가 수정할 수 없는 `/opt/hangeul-swipji-controller/automation/ai_agent_runner.py`로 ExecStart 교체**를 추가하는 systemd drop-in. 상시 호스트가 없으면 **설치/활성화하지 않는다**.

## 실제 상시 호스트 관리자 작업 (아직 수행 안 됨)

1. 네트워크 연결된 Linux 호스트와 **재부팅 후에도 남는 별도 볼륨** `/var/lib/hangeul-swipji`를 준비하고 `hangeul-worker` 계정에 해당 볼륨 및 격리 `/srv/hangeul-swipji` 작업트리만 쓰기 권한 부여. `home` 폴더를 볼륨에 생성한다. GitHub 저장소를 정확한 격리 SHA로 배치하되 `main`에 push/merge하지 않는다.
2. 호스트에 Python 3, git, **실제 인증 가능한 Codex CLI**를 설치한다. `/opt/hangeul-swipji-controller/automation`에 검증된 중앙 SHA의 `ai_agent_runner.py`, `work_request_worker.py`, `continuous_dispatcher.py` 등 실행 의존 파일을 root 소유 읽기 전용으로 배치한다. **중앙의 정확한 검증 SHA에서 가져온 실행 파일과 Python import 경로를 고정**하고 작업자에게 `/opt/hangeul-swipji-controller` 쓰기 권한을 부여하지 않는다. `/etc/hangeul-swipji/queue-sync.env`는 root 소유 `0600`으로 별도 생성하고 `GITHUB_REPOSITORY`, `HS_DURABLE_WORKER_DB`, GitHub **읽기 전용** `GH_TOKEN`만 포함한다. 이 파일에는 `OPENAI_API_KEY`나 GitHub 쓰기 토큰을 넣지 않는다. `/etc/hangeul-swipji/worker.env`를 루트 소유 `0600`으로 만들고 `GITHUB_REPOSITORY=anigio2705-dev/hangeul-swipji`, `HS_DURABLE_WORKER_DB=/var/lib/hangeul-swipji/queue.sqlite3`, `HS_WORKTREE=/srv/hangeul-swipji`, `OPENAI_API_KEY`, 최소 권한 `GH_TOKEN`을 설정한다. 값은 Git/Issue/Actions 로그에 기록하지 않는다. `git push` 인증은 agent에 전달하지 않고 controller만 사용하도록 별도 점검한다.
3. `automation/deploy/host-preflight.sh`를 **root가 직접 검토한 후** `/usr/local/libexec/hangeul-swipji/host-preflight.sh`로 복사한다. `/usr/local/libexec/hangeul-swipji` 디렉터리와 스크립트는 root 소유, group/other 쓰기 금지(예: 디렉터리 0755, 파일 0755)로 설정한다. 작업자 계정이 이 경로·상위 디렉터리·systemd unit을 수정할 수 없어야 한다. **AI 작업트리 안의 동일 파일을 ExecStartPre에서 실행하지 않는다.** 이 guard는 서비스 시작 시의 검사일 뿐 실행 도중 설정 변조·AI 작업자와 controller 간 OS 수준 비밀키 격리를 대체하지 않는다. Codex/작업자에게 GitHub 쓰기 토큰이 포함된 환경을 상속시키지 말고, 중앙의 최소권한 controller를 별도 사용자/컨테이너로 분리한 후 독립 QA를 수행한다. 현 `worker.env`와 worker 프로세스의 실제 비밀키 격리는 미입증이다.
4. 두 sync unit을 `/etc/systemd/system/`에, drop-in을 `/etc/systemd/system/hangeul-ai-worker.service.d/`에 설치한다. `systemctl daemon-reload` 후 `systemd-analyze verify` 및 `bash -n`을 수행한다. **중앙의 heartbeat/fencing/remote push QA가 완료되기 전에는 AI worker를 활성화하지 않는다.**
5. 중앙 승인된 격리 환경에서 먼저 `systemctl start hangeul-queue-sync.service`, `journalctl -u hangeul-queue-sync.service`로 실제 GitHub open issue→SQLite ingest/reconcile을 확인하고, 재시작 후 DB 보존·동시 claim 방지·GitHub 403/429/503·닫힌 이슈 취소를 시험한다. 이어 중앙과 15팀이 별도 정확 SHA 검증을 완료한 후에만 `systemctl enable --now hangeul-queue-sync.timer` 및 `systemctl enable --now hangeul-ai-worker.service`를 검토한다.
6. 이벤트 **즉시** 실행에는 공개 HTTPS 수신기와 HMAC 서명 검증, 재전송 중복키, 허용 이벤트/저장소 제한, 2xx ack 후 영속 enqueue가 별도로 필요하다. 현재 이 구성은 **미구현**이며 30초 polling을 이벤트 즉시 실행이라고 주장하지 않는다.
7. 24시간 관측은 실제 `systemctl show` 활성/재시작 횟수, `journalctl --since ...`, DB 작업번호/lease token, Codex 호출 ID, 제품 코드 이전/이후 SHA, 원격 PR/CI run_id, 15팀 QA_PASS/FAIL, 중앙 READY 및 다음 작업 승계의 시간별 연속 로그를 보관한다. 24시간 미경과 시 `24H_PROVEN=0`.

## 명시적 BLOCKED

외부 호스트 접속/배포 권한, 영속 볼륨, 실제 Codex 인증키·CLI, GitHub 쓰기 토큰의 호스트 안전 주입, HTTPS webhook 수신기 및 실제 24시간 관측은 이 GitHub PR만으로 확보되지 않는다. 해당 권한·환경 확인 전에는 `HOST_DEPLOYED=0`, `REAL_AI_CALLS=0`, `24H_PROVEN=0`. #101 INTERNAL_READY, #102 QA_PASS, #103 가상 산식 INTERNAL_READY는 보존한다.

## 2026-10-31 보안 보완 및 미해결 위험

PR #168의 queue sync는 agent-editable worktree 대신 root-owned controller snapshot과 읽기 전용 GitHub credential을 요구한다. 배치 시 실제 파일 권한/의존성 검증이 필요하다. host guard는 이제 root-owned host copy를 요구하며, effective fetch/push URL을 각각 모두 검사하고 여러 목적지·불일치를 차단한다. 이는 GitHub Actions 정적 검사 대상이지 실제 서버에서 root ownership/재시작/키 격리까지 입증한 것은 아니다. 중앙 PR #162의 실행 중 Git config 변조·credential helper/SSH command 위험은 **중앙이 독립 QA와 함께 별도 해결**해야 한다. 이 지원 PR은 중앙 runner를 변경하지 않으며 독립 QA_PASS 또는 호스트 GO 판정이 아니다. 신규 유료 서버 생성, main 변경, 실결제, 운영 데이터 변경 금지.

## 2026-10-31 15:33 KST 추가 P0 보안 병목: 실행 코드 변조

PR #162 기본 `hangeul-ai-worker.service`는 `ExecStart=/usr/bin/python3 -u /srv/hangeul-swipji/automation/ai_agent_runner.py`로 AI가 편집하는 worktree 안의 **컨트롤러 자체**를 실행했다. 에이전트가 그 파일을 수정하고 서비스가 재시작되면 컨트롤러 인증정보를 가진 프로세스가 변조된 코드를 실행할 수 있다. 기존 root-owned preflight guard만으로는 방어할 수 없다.

PR #168 지원 drop-in에서 `ExecStart=`를 초기화하고 root-owned `/opt/hangeul-swipji-controller/automation/ai_agent_runner.py`로 대체했으며 `PYTHONPATH`/`WorkingDirectory`도 보호된 경로로 전환했다. preflight는 컨트롤러 경로·의존 파일의 root 소유, symlink 금지, group/other 쓰기 금지를 확인한다. 격리 CI는 실행 경로가 작업자 쓰기 영역으로 되돌아가지 않았는지 검사한다. **이 변경은 실제 호스트 적용이나 동일 UID 내 credential 격리 증거가 아니다.** AI 프로세스와 GitHub 쓰기 credential을 가진 컨트롤러를 별도 OS 사용자/컨테이너 및 최소권한 broker로 분리하고 B/15팀이 실증 검증하기 전에는 AI 워커를 활성화하지 않는다.


## 2026-10-31 16:33 KST — C팀 GitHub issues 즉시 수신기 (코드만, 미배포)

- `automation/deploy/issue_webhook_ingress.py`: GitHub `issues` opened/reopened/edited/closed 서명 HMAC-SHA256 및 저장소 검증, 최대 256KiB 본문, delivery UUID 중복 억제, 기존 영속 SQLite 작업 큐에 즉시 ingest, closed 시 lease 취소 기록. 같은 호스트의 30초 polling은 백업/재조정 경로로 유지.
- `automation/deploy/test_issue_webhook_ingress.py`: 서명 위조 차단, 다른 저장소 거부, 중복 delivery 멱등성, 영속 큐 저장, 중복 활성 요청 차단, closed 취소 등 7개 회귀 테스트. CI는 **실제 중앙 DurableWorkStore**와 함께 테스트한다. 가짜 GitHub 이벤트는 운영 실증이 아니다.
- **절대 미완료:** HTTPS 공개 수신기·GitHub webhook 등록/전달, 수신기 서비스 별도 OS 계정과 HMAC 비밀 분리, 실제 host 재시작 복구, `workflow_run` CI→B QA 이벤트/중앙 READY→다음 과제 승계, 인증 Codex 두 과제, 24h 관측. `workflow_run`은 현재 202 ignored이며 QA 자동 승계로 보고하지 않는다.
- **안전한 배치 선행조건:** webhook 전용 비밀을 AI 작업자/컨트롤러 자격증명과 분리한 별도 OS 사용자, 영속 큐의 명시적 최소권한 IPC/ACL, 외부 HTTPS 리버스 프록시, HMAC secret 32자 이상, GitHub `issues` 이벤트만 허용. 수신기는 `127.0.0.1:8778/github/issues`에만 bind. 공개 HTTPS, ACL, HMAC 회전, queue-sync와 동시 실행 정합성에 대한 독립 검증 전 서비스 활성화 금지.
- **보안 경계:** signed closed 이벤트의 SQLite lease 취소는 중앙 #162의 취소↔push 원자성 문제를 해결하지 않는다. #174 QA_FAIL 유지. 실제 push broker/fencing 분리 및 15팀 exact-SHA 독립 재검증 전 워커 활성화 금지.
