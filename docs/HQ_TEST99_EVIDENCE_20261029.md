# 테스트용99 수락 관문 — 독립 탐색 및 실패 재현 (2026-10-29)

- 공식 운영 Pages: https://anigio2705-dev.github.io/hangeul-swipji/ (main 게시).
- **기존 테스트99 실제 문서 기록 URL:** https://hangeul-swipji99-test.onrender.com (Render Free, Singapore, Python, autoDeploy off).
- **기록된 과거 배포:** audit/staging99-deployment.json — 2026-10-27 13:27 KST, commit ad5757d9327a6871b70649da081d5cefb8a1a74b. 해당 SHA는 현재 배포 SHA라는 증거가 아니다.
- **기록된 후속 경계 HTTP 검사:** audit/staging99-origin-hosted.json — 2026-10-27 07:34 UTC, /healthz 200, mode=test, scope=isolated-staging, Basic gate 401, 외부 Origin 403; 로그인 뒤 브라우저·모바일 검증은 미실행.
- **관련 소스 브랜치:** team11/d1-staging99-identity-20261028, integration/issue4-staging-preview-20261028. 이들은 **테스트99의 현재 Render 배포 브랜치로 검증된 것이 아니다**.
- **구성 제안:** deploy/render-staging.yaml은 integration/phase2-phase3-20261027 브랜치와 autoDeployTrigger off를 가리킨다. Render 대시보드의 현재 서비스 설정 확인 전에는 이를 실배포 설정으로 간주하지 않는다.
- **권한 차단:** Render 관리 권한/환경변수/배포 로그를 이 GitHub-only 실행에서 확인하지 못했다. 기존 서비스에 임의 배포하지 않았다.
- **실접속:** 자동화 실행 환경에서 테스트99 /healthz 접속 시 웹 도구는 접근 오류, 셸은 DNS 이름 확인 실패. GitHub Actions의 별도 공개 HTTPS probe 아티팩트로 추가 독립 확인한다. 이 결과는 인증 후 화면 재현을 대체하지 않는다.
- **수락 로직:** automation/hq_test99_gate.py + 9개 반례 검사. 과거 URL·CI PASS만으로 수락 금지; 실제 호스트 해시·배포 SHA·실제 격리 설정·인증 브라우저·모바일·대표 승인 모두 별도 필수.
- **자동 반영 정책:** main/운영DB/실결제/운영 홈페이지 무변경. 테스트99 현재 배포 SHA 및 격리된 Render 서비스 확인 전에는 자동 배포하지 않는다.
- **방법론:** OpenAI Agent Improvement Loop (https://developers.openai.com/cookbook/examples/agents_sdk/agent_improvement_loop)의 실패 사례→재현 평가를 적용해 과거 배포를 최신이라고 오인하는 회귀를 막는다.
- **상태:** URL 식별 완료 / 현재 호스팅 상태·배포 SHA 미검증 / 코드 검증 13/160 유지 / 실사용 수락 0/160 / 최종 승인 0/160.
