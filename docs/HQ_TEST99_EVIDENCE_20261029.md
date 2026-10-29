# 테스트용99 수락 관문 — 독립 탐색 및 실패 재현 (2026-10-29)

- 공식 운영 Pages: https://anigio2705-dev.github.io/hangeul-swipji/ (main 게시).
- **기존 테스트99 실제 문서 기록 URL:** https://hangeul-swipji99-test.onrender.com (Render Free, Singapore, Python, autoDeploy off).
- **기록된 과거 배포:** audit/staging99-deployment.json — 2026-10-27 13:27 KST, commit ad5757d9327a6871b70649da081d5cefb8a1a74b. 해당 SHA는 현재 배포 SHA라는 증거가 아니다.
- **기록된 후속 경계 HTTP 검사:** audit/staging99-origin-hosted.json — 2026-10-27 07:34 UTC, /healthz 200, mode=test, scope=isolated-staging, Basic gate 401, 외부 Origin 403; 로그인 뒤 브라우저·모바일 검증은 미실행.
- **관련 소스 브랜치:** team11/d1-staging99-identity-20261028, integration/issue4-staging-preview-20261028. 이들은 **테스트99의 현재 Render 배포 브랜치로 검증된 것이 아니다**.
- **구성 제안:** deploy/render-staging.yaml은 integration/phase2-phase3-20261027 브랜치와 autoDeployTrigger off를 가리킨다. Render 대시보드의 현재 서비스 설정 확인 전에는 이를 실배포 설정으로 간주하지 않는다.
- **권한 차단:** Render 관리 권한/환경변수/배포 로그를 이 GitHub-only 실행에서 확인하지 못했다. 기존 서비스에 임의 배포하지 않았다.
- **실접속 재검증:** 자동화 직접 웹 도구는 접근 오류, 셸은 DNS 이름 확인 실패였지만, **2026-10-29 16:00:29 KST GitHub Actions #40832650710의 독립 HTTPS GET에서는 /healthz 200**, `mode=test`, `scope=isolated-staging`, origin 일치, **비인증 홈 401**을 확인했다. 도구별 접근성 차이를 구분한다. 실제 로그인 뒤 화면·모바일은 여전히 미검증.
- **현재 코드 불일치:** 호스팅 `sourceSHA256=e9d1368308005470c4e6cbf04e1d237eeb61ff1d0abc0f01c14558a90ee8b755`; 이번 격리 코드 `phase3/staging_server.py` SHA256 `ed0101f530d46b1d8d097ed25a061267854df672f91be03f99a6677f2067a9a6`. 서로 다르다. 현재 Render 배포 커밋은 여전히 불명. 10월 27일 과거 기록을 현재 SHA로 대체하지 않는다.
- **수락 로직:** automation/hq_test99_gate.py + 11개 반례 검사. 과거 URL·CI PASS만으로 수락 금지; 실제 호스트 해시·배포 SHA·실제 격리 설정·인증 브라우저·모바일·대표 승인 모두 별도 필수.
- **자동 반영 정책:** main/운영DB/실결제/운영 홈페이지 무변경. 테스트99 현재 배포 SHA 및 격리된 Render 서비스 확인 전에는 자동 배포하지 않는다.
- **방법론:** OpenAI Agent Improvement Loop (https://developers.openai.com/cookbook/examples/agents_sdk/agent_improvement_loop)의 실패 사례→재현 평가를 적용해 과거 배포를 최신이라고 오인하는 회귀를 막는다.
- **실제 CI:** #40832562392 최초 9개 테스트 PASS 및 비인증 HTTP 관측 BLOCKED; #40832639204는 새 origin/401 조건만 먼저 추가되어 fixture 미갱신으로 FAIL; 정확한 재검증 #40832650710 (SHA `3da528d3b23d5d0a4d80d6bfd82633a8bdd9ab43`) **11개 PASS**, 호스팅 200/401 확인, 수락 판정 **BLOCKED**. CI 성공은 테스트99 반영 성공이 아니다.
- **상태:** 테스트99 URL 및 공개 경계 실접속 확인 / 호스팅 소스 해시 불일치·현재 Render 배포 SHA 미확인 / 인증 후 PC·모바일 미검증 / 코드 검증 13/160 유지 / 실사용 수락 0/160 / 최종 승인 0/160.
