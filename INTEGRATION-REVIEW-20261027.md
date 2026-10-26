# 한글쉽지 2차 + 3차 통합 검증 — 2026-10-27 KST

판정: **별도 통합 브랜치의 실행 가능한 로컬 통합 완료. 운영 전환 미완료.** main 병합, 운영 배포, 운영 Supabase 변경, 실제 결제·정산은 하지 않았다.

## 확인한 원본과 통합

- main: `fe9759fd0f60f20e784fae1d3d95625b63db1d93`; 코드 커밋 `4b6e7923c6fa1e0de2b0b4f3e2df133e9870f856` 확인.
- 3차: `31a10c54e564cae232d2909185438c784c9241e0` 확인.
- GitHub Actions 실제 조회: 2차 코드 검사, main Pages, 3차 격리 검사 모두 success. 이전 실행 결과와 이번 로컬 검사를 구분한다.
- 통합 브랜치: `integration/phase2-phase3-20261027`. main에서 생성하여 3차를 이력 보존 병합. 텍스트 충돌 0개. 3차는 phase3 디렉터리와 전용 CI 추가여서 무료 콘텐츠와 겹치지 않았다.

## 실제 연결

홈페이지의 기존 히어로·6카드·통합 구역·다국어 스크립트를 유지하고 학습 도구에 강사 수업 진입 링크 하나를 추가했다. 학습관→무료 진단→강사 수업 안내→테스트 스튜디오를 연결했다. 무료 진단의 0~6 권장 단계만 URL로 전달하며 개인정보·정답·인증 정보를 옮기지 않는다. CEFR 등급으로 자동 환산하거나 예약 권한에 사용하지 않는다.

3차 서버가 `/free/`에서 기존 무료 사이트의 공개 파일만 제공한다. 스튜디오에서 무료 학습·읽기·진단으로 돌아갈 수 있다. 정적 GitHub Pages에서는 서버가 실행되는 것처럼 가입·예약 버튼을 제공하지 않고 실행 방법을 표시한다. 통합 서버는 기존대로 loopback만 수신한다.

강사·학습자·파트너 가입, 프로필 승인, 검색, 일정, 예약, 모의 결제, 공유 교재, 화상방 링크, 출석, 과제, 평가/피드백, 완료, 후기, 관리자 모의 정산/환불/이의신청은 기존 3차 구현을 보존하여 실행 검증했다. 교재12개·평가36개와 예약 데이터는 무료350단원·퀴즈1758개·읽기600개와 별도 파일/SQLite에 유지된다. Supabase 설계 SQL과 PG/Auth 어댑터는 수정·적용하지 않았다.

## 검사와 재비판

|검사|결과|한계|
|---|---|---|
|Python 단위·HTTP·권한·예약·결제 계약·콘텐츠·공개파일 검사|49/49 통과|격리된 임시 SQLite·모형 Auth/PG|
|격리 PostgreSQL/PGlite|12항목 통과|호스팅 Supabase·PostgREST/JWT 검증 아님|
|통합 Chromium UI|23항목 통과|모의 서버 시계로 겹친 출석30분; 실제 통화 아님|
|무료/진입 페이지 화면|PC1440·모바일390 각각13페이지 통과|모바일 에뮬레이션, 실물 장치 아님|
|무료 수업·언어·진도·읽기·미디어 기능|PC·모바일 모두 통과|음성78개씩 재생 종료; 실제 청취 승인 아님|
|350단원·1758문항·읽기600개/1800문항·발음 실패·유사성·페이지·기초|소스 검사 통과|교육 효과·공식 난이도 인증 아님|

Self-Refine에서 홈페이지 보존 검사의 통합 링크 충돌을 확인했다. 기존 홈페이지와 바이트 비교하되 **정확히 승인된 링크 한 개만 제거했을 때 원본과 동일해야** 통과하도록 수정했다. 임의 화면 변경을 허용하지 않는다.

Kill Critic 재검사에서 CSS의 `display:inline-block`이 HTML `hidden`을 덮어 정적 안내에서 실행 불가 버튼이 보이는 오류를 재현했다. `[hidden]{display:none!important}`로 수정하고 PC·모바일 정적 페이지 검사에 회귀 조건을 추가했다. 언어 스크립트가 링크에 쿼리를 붙이는 기존 동작도 반영해 브라우저 검사를 고쳤다.

새 무료 파일 제공 경로는 고정 allowlist로 제한했다. Python·SQL·DB·환경파일·Git 설정·phase3 원본 콘텐츠·경로탈출·미등록 파일의 HTTP 노출 차단을 재검사했다. 악의적 stage 값은 무시한다. 기존 IDOR·CSRF·역할상승·중복 거래·동시 예약·겹치지 않은 출석 완료 차단 검사도 통과했다.

브라우저 결과: `phase3/browser-results.json`, `phase3/postgres-results.json`, `audit/browser-functional.json`. 재현: `.github/workflows/integration-validation.yml`. 통합 브랜치 push에서 검사만 실행하며 배포 작업을 포함하지 않는다.

## 실행

```bash
python3 phase3/server.py
# 출력된 주소 + /free/index.html 에서 무료 교육부터 시작
python3 -m unittest discover -s phase3 -p 'test_*.py' -v
npm ci --prefix phase3 --ignore-scripts
node phase3/postgres-test.cjs
node phase3/browser-test.cjs
NODE_PATH=./phase3/node_modules node scripts/browser-smoke-phase2.cjs
```

브라우저 검사에는 Playwright Chromium 설치가 필요하다. 테스트는 임시 데이터만 생성한다. 기존 운영 계정·DB를 복사하지 않는다.

## 남은 오류·운영 전 작업

- 기존 필수 발음359개 누락, 보류57개, 실제 청취 승인0개. 완료 게이트는 여전히 실패가 정상이다. 누락을 통합 완료로 숨기지 않았다.
- 실제 PC↔휴대폰 Jitsi 음성/영상, 인증된 전용 회의실과 서버 출석 증빙 미검증.
- 호스팅 Supabase의 실제 Auth·JWT·RLS·이메일 확인·복구·세션 회수는 별도 격리 프로젝트에서 검증 필요. 운영 DB는 사용하지 않았다.
- 실 PG sandbox 계정·서명 webhook·환불 대사는 외부 자격증명 필요. 실제 금전 이동 없음.
- 자가선택 강사/파트너의 미승인 지도서 열람은 기존 3차 정책을 유지했다. 전문 교재 제한 정책과 자격/연령/신원·계정 정지 정책 확정 필요. 로컬 승인으로 실제 자격을 인증하지 않는다.
- 실제 강사/학습자 파일럿, 실물 Android/iPhone, 외부 언어 번역 의미 검수, 법률·세무·결제사업자 검토와 운영 호스트 준비가 남았다.
- 기존 무료 다국어 스크립트는 유지했다. 3차 UI는 기존 한국어 중심이며 8개 언어 전문 번역 완료를 주장하지 않는다.
- 운영 전 전체 보안·부하·백업/복구 검증 필요. 이번 검사는 전체 보안 인증이 아니다.
- 사용자 승인 전 main 병합 및 실제 운영 배포 금지.

## 이번 연결 수정 파일

`index.html`, `learn.html`, `placement.html`, `teaching-platform.html`, `teaching-entry.js`, `phase3/app.js`, `phase3/index.html`, `phase3/server.py`, `phase3/free-public-files.json`, `phase3/test_free_mount.py`, `phase3/browser-test.cjs`, `scripts/audit-phase2-content.cjs`, `scripts/browser-smoke-phase2.cjs`, `.github/workflows/integration-validation.yml` 및 검사 JSON/이 보고서. 기존3차37개 파일은 원본 브랜치 이력과 함께 통합했다.
