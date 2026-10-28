# 한글쉽지11 — 제1호 명령 1차 D1 실행 인계

- 날짜: 2026-10-28
- 브랜치: `team11/d1-staging99-identity-20261028`
- 서버 수정 커밋: `4015fac37ad23577a1cdf77f47412a1c7f95703b`
- 신규 테스트 커밋: `bc80797b1c470aaa85c5359caa28cabfc623501e`
- 수정: `phase3/staging_server.py`의 `/healthz`에 `deploymentCommit`을 추가. `RENDER_GIT_COMMIT` 또는 `HS_STAGING_BUILD_SHA`가 **정확한 40자리 16진 SHA**일 때만 표시하며, 누락/잘못된 경우 null.
- 추가 테스트: `phase3/test_common_staging_deployment_identity.py`; 정상·누락·오류·대체 SHA 4가지 테스트 메서드. 테스트 파일 작성 완료, **GitHub Actions 실행/성공 미확인**.
- 99서버: https://hangeul-swipji99-test.onrender.com/healthz ; 현재 외부 조회 접근 실패. **실제 배포 SHA 미확인, 서버 검증 미완료**.
- Render 문서의 과거 최초 SHA `ad5757d`는 현재 배포 SHA로 취급하지 않음.
- 데이터 영속성: 기존 `deploy/STAGING99.md`에서 Render Free 임시 SQLite 경로 `/tmp/hangeul-swipji-staging/platform.sqlite3` 사용 기록 확인. 재시작/재배포 시 데이터 손실 위험. 현재 Render 디스크/DB 설정은 권한 없어 확인 불가. **실제 DB를 변경하거나 재배포하지 않음**.
- API 계약: 기존 `/api/register`, `/api/login`, `/api/logout`, `/api/free-progress`, `/api/free-progress/import`, `/api/free-progress/quiz`, `/api/free-progress/position`, `/api/teachers`, `/api/bookings`, `/api/admin/verify`, `/api/instant/*` 경로 보존. 외부 팀 연동 회귀검사는 미실행.
- 이번 작업은 **서버 상태 신원 확인용 코드 수정**이며 99서버 정상화 완료나 E2E 성공 선언이 아님.

## [대표 조치 요청]
- 필요한 작업: 기존 Render `hangeul-swipji99-test` 서비스에 대한 배포 및 환경설정 확인 권한 제공 또는 관리자가 현재 Deploy SHA/디스크 설정 확인
- 사람이 필요한 이유: 현재 연결된 GitHub 접근 권한은 Render 서비스 관리자 권한을 포함하지 않음
- AI가 이미 수행한 작업: /healthz SHA 식별 코드 및 자동 테스트 추가, GitHub 반영
- 대표가 직접 해야 할 일: Render 서비스 접근 연결/권한 부여. 비밀번호·비밀키를 채팅/GitHub에 게시하지 말 것
- 예상 소요시간: 접근 권한 확인 5~10분(관리자 사정에 따라 달라짐)
- 조치하지 않으면 막히는 기능: 현재 99서버 배포 SHA 검증, 안전한 배포 및 실브라우저 최종 검증
- 가능한 대체 방법: Render 관리자가 서비스 Deploys 화면의 SHA/디스크 상태만 확인해 전달; 단 배포는 권한 보유자가 실행

## D2 선행 과제
1. 기존 Render DB 손실 대책 확인 후에만 통합 브랜치 최신 코드 배포.
2. 15팀에 11팀 SHA/헬스 체크 계약 전달.
3. HTTP 회원가입→로그인→진도→로그아웃→재로그인→예약/즉시 매칭 회귀검사 실행.
4. 99서버 /healthz, 관리자, 실브라우저 검증과 CI 성공 로그 수집.
