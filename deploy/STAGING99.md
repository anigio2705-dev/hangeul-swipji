# 한글쉽지99 통합 테스트 호스팅 준비

기준일: 2026-10-27 KST. 시작 HEAD `1928a342ff401ed18232bfa4d025b33547b7e0f9`.
**배포 설정과 로컬 검사를 준비한 상태이며 외부 테스트 주소는 아직 발급하지 않았다.**

## 기존 결과와 실제 실행 구조

통합 브랜치에서 AGENTS.md·GLOBAL_MASTER_PLAN.md·DEVELOPMENT_STATUS.md·PROFESSIONAL96-REVIEW-20261027.md 및 docs/education/의5개 문서를 읽었다. GitHub 최신4개 브랜치가 인수인계 값과 일치했다. `1928a34`의 CI [40440214531](https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40440214531)는 completed/success이며 integration-evidence 아티팩트12705133726이 보존되어 있다.

Python 표준 라이브러리 HTTP 서버·SQLite·기존 정적 홈페이지가 한 프로세스/같은 출처로 실행된다. Python 런타임 의존 패키지는 없다. Node/Playwright/PGlite는 검사 도구다. 기본 `server.py`는 여전히127.0.0.1 전용이다. GitHub Pages는 이 Python API를 실행하지 않는다. Sites는 Workers/HTTP 환경으로 이 서버를 그대로 실행하는 호스트가 아니며, 이번 요구에 맞추려고 서버를 재개발하지 않는다.

기존 index.html·홈 디자인·교재·음원·교육 원본을 변경하지 않는다. staging_server.py가 별도 테스트 실행 경계를 추가한다. `/`는 동일 index.html, 기존 화상대화 경로는 **테스트 서버에서만** `index.html#teaching-platform`으로 이동한다.

## 연결·비용·선택지 — 아직 호스팅 선택/구매하지 않음

계정 조사 범위: 현재 제공되는 연결 도구, 사용 가능한 플러그인 검색, Sites 소유 목록. Render·Railway 플러그인은 검색되었지만 둘 다 미연결이다. 사용자가 두 회사 계정을 이미 보유하는지는 미확인이다. 기존 Sites 목록에는 별개 리딩 다운로드 사이트만 있다. 호스팅 토큰을 검색하거나 출력하지 않았다.

|구성|예상 비용(USD, 세금/초과 사용 별도)|필요 계정·권한|제약|
|---|---|---|---|
|Render Free Python+임시 SQLite|무료 할당 안에서 서버 $0|Render 계정/플러그인 연결, 새 Web Service 생성 권한. Blueprint를 쓰면 GitHub 저장소 연결 권한 확인|15분 무접속 시 중지, 재시작 약1분. 중지/재시작/재배포 시 계정·예약·과제 등 테스트 DB 소실. 워크스페이스 월750시간 공유. 영구 디스크 불가|
|Render 유료 0.5c-512mb+1GB 디스크|공개 요금 기준 월약 $7.25($7+$0.25), 확정 견적 아님|위 권한+결제 수단·사용자 비용 승인|같은 Python/SQLite를 지속 보존. 단일 인스턴스·소수 테스트용, 대규모/운영 인증 아님|
|Railway Python+볼륨|Hobby 최소 월 $5, 사용량 초과분 추가. 무료/Trial 자격·잔액 별도 확인|Railway 계정/플러그인 연결·프로젝트/볼륨 권한, 유료 선택 시 결제 승인|계정별 무료 한도와 실제 CPU/RAM/볼륨 비용을 연결 후 확인. 비용 상한·한도 도달 시 동작 확인 필요|

우선 검토안은 **비용 승인 없이 확인 가능한 Render Free**다. 기록이 사라지는 조건을 수용할 때만 선택한다. 며칠 동안 같은 예약/과제를 보존하려면 유료 디스크 또는 다른 지속 저장 구성을 별도로 승인받는다. 무료 설정을 승인 없이 유료로 바꾸지 않는다. 새 테스트 서비스 외 기존 홈페이지·main·운영DB·실제금전은 승인 범위에 포함되지 않는다.

공식 확인 출처(2026-10-27 조회):

- https://render.com/docs/free — 중지/초기화/무료 시간·대역폭/빌드 할당. 카드/초과 청구·정지 조건은 연결된 계정의 실제 설정에서 재확인한다.
- https://render.com/pricing — 공개 요금. 가격표 일부는 동적 페이지여서 검색 인덱스의 공식 페이지 요금도 대조했으며 서비스 생성 화면에서 최종 재확인해야 한다.
- https://render.com/docs/disks — 유료 서비스만 영구 디스크 부착 가능.
- https://render.com/docs/blueprint-spec — 비기본 Blueprint 경로·branch·autoDeployTrigger·환경변수.
- https://docs.railway.com/pricing/plans — Hobby $5 포함 사용량/초과분·볼륨 요금.

## 준비한 실행 경계

- `phase3/staging_server.py`: 제공업체 HTTPS 프록시 뒤에서0.0.0.0:$PORT 실행. 정확한 HTTPS origin/Host 확인, 외부 출처 POST 거부. X-Forwarded-*만으로 호스트를 신뢰하지 않는다.
- 모든 홈/자산/API는 별도 Basic Auth 비밀번호 필요. 세션 쿠키는 Secure/HttpOnly/SameSite=Strict. DB 점검만 하는 `/healthz`는 게이트 제외다. 이 점검은 사용자·교재를 반환하지 않는다.
- 테스트 DB는 소스 밖 `hangeul-swipji-staging/*.sqlite3` 전용 경로. 운영 DB/외부 인증·결제 환경변수가 있으면 시작 거부. 외부 Auth/Stripe API도 테스트 서버에서 차단한다. 결제·정산은 기존 모의 원장만 사용한다.
- 기존 `speaking-config.js`에 호스팅 Supabase 공개 설정이 있음을 발견했다. **원본은 보존**하고 테스트 응답에서는 빈 설정으로 대체한다. 기존 화상 페이지도 테스트 수업으로 이동시킨다. CSP connect-src self로 정적 페이지의 외부DB 통신까지 차단한다. 운영 Supabase에 접속/쓰기/SQL 적용하지 않았다.
- 신규 가입은 `name@example.test` 주소만 허용한다. 실명·실제 연락처·카드번호·신분증을 입력하지 않는다. no-store/noindex를 설정한다.
- 관리자 `admin@example.test`는 별도 환경변수 비밀번호로 최초1회 생성. 반복 시작 때 중복 생성/비밀번호 강제 초기화하지 않는다. 기존 비밀번호와 환경변수가 다르면 시작을 거부한다.
- 기본 로컬 서버는 기존 동작을 유지한다. 새로운 경계 추출과 선택적 Secure 쿠키 추가 외 업무 로직을 바꾸지 않았다.

이 구성은 접근을 제한한 소수 사용자 테스트다. Python http.server를 운영 보안/부하 검증 완료 서버로 인증하지 않는다. 모든 보안 위협·백업 복구·실물 기기·실제 화상 미디어 검증을 마쳤다는 뜻이 아니다.

## 계정 연결 후 실제 배포 순서

1. Render 플러그인을 연결한다. 계정/워크스페이스/생성 권한과 무료/청구 조건을 읽기 조회한다. 토큰·비밀번호를 채팅이나 GitHub에 붙이지 않는다.
2. 새 테스트 Web Service 하나만 만든다. 기존 운영 서비스·도메인은 선택하지 않는다. 소스는 이 통합 브랜치의 **검사한 커밋**으로 고정하며 main을 선택하지 않는다.
3. 제안 파일 `deploy/render-staging.yaml`을 사용한다. 이 파일이 저장소에 있다는 것만으로 배포되지 않는다. Blueprint는 기본 경로가 아니므로 경로를 명시한다. 무료 플랜, Singapore, 자동 배포 off, 시작 명령 `python3 phase3/staging_server.py`, health `/healthz`를 확인한다. Python3.12.14는 이번 로컬 검사 버전이며 호스트 지원 여부도 확인한다.
4. 환경변수: `HS_STAGING_USER=review`, 독립 자동생성 `HS_STAGING_PASSWORD`/`HS_STAGING_ADMIN_PASSWORD`, `HS_STAGING_DB=/tmp/hangeul-swipji-staging/platform.sqlite3`. 제공업체 `RENDER_EXTERNAL_URL`을 HTTPS origin으로 사용한다. 다른 제공업체면 `HS_STAGING_ORIGIN`을 후행 / 없는 정확한 HTTPS origin으로 설정한다. `HS_PHASE3_DB`, DATABASE_URL, Supabase/Stripe 환경변수는 주입하지 않는다.
5. 유료 영구 저장이 따로 승인되면 플랜/디스크 생성안을 다시 검토하고 DB 경로를 `/var/data/hangeul-swipji-staging/platform.sqlite3`로 바꾼다. 이 문서의 무료 제안 파일은 그대로 유료 변경을 수행하지 않는다.
6. 배포가 성공하면 **반환된 실제 URL**로 PC/모바일 접속, 게이트401/로그인, 홈/무료/진단, 강사 가입·관리자 승인·가능 시간, 학생 검색·96교재·예약·모의 결제·과제·평가·재예약을 확인한다. 외부 요청/DB 차단·세션·재시작 데이터 초기화 조건도 확인한다. 확인 전 URL이나 성공을 추정하지 않는다.
7. 접속 비밀번호는 호스팅 비밀값 UI에서 안전하게 확인하고 원장님 PC/휴대폰에 입력한다. 플랫폼 안에서는 별도 학습자/강사/관리자 계정을 사용한다. Basic Auth는 브라우저별로 유지될 수 있으므로 공용 기기에서는 별도 브라우저 세션을 종료한다.

## 접속 현황과 잔여 과제

외부 테스트 URL: **미발급**. 접속 조건: 호스팅 연결/생성 후 HTTPS+게이트 비밀번호, 기능별 테스트 계정. localhost는 원장님 휴대폰에서 접속할 공개 주소가 아니다.

이번 자동 검사 결과는 `audit/staging99-verification.json` 및 해당 커밋 CI와 함께 확인한다. 외부 배포 후 실제 URL/호스트/배포 커밋/검사 시각을 DEVELOPMENT_STATUS.md에 추가한다. 소스 원본과 브랜치 보존은 Git diff/검사로 확인한다.

실제 교사96수업 검수·학습 효과, 사람 녹음359개·청취 승인0, 두 기기 화상·신뢰 출석, Android/iPhone, 운영Auth/RLS·부하·복구, 전문 전체8언어, 실제결제/정산, 운영배포는 계속 미완료다. 과거 한글쉽지1~7 전문은 **대화 원본 확인 필요**다.
