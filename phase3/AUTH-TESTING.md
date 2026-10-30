# 인증·PostgreSQL 테스트 범위 — 2026-10-27

## 실제로 실행한 검사

`node phase3/postgres-test.cjs`는 PGlite 0.5.12의 **실제 PostgreSQL WASM 엔진**에 `supabase-preview.sql` 전체를 설치한다. 운영 DB·Supabase 계정·외부 네트워크를 사용하지 않는다. `anon`, `authenticated`, `auth.users`, `auth.uid()`는 명시적인 테스트 모형이다. 이는 PostgreSQL의 grants/RLS/제약 실행 검사이며 호스팅 Supabase Auth·PostgREST·JWT·네트워크 권한 검증이 아니다.

검사: 격리 설치 게이트, 전 테이블 RLS, 무권한 스키마 거부, 테스트용 SELECT grant 후 자기 행 조회, 역할 변경 거부, 참여자/비참여자의 예약·과제·원장 경계, 원장 쓰기 거부, 강사 시간 겹침과 다른 강사 사이 학습자 시간 겹침, 중복 원장 이벤트. 테스트용 grant는 이 로컬 일회성 인스턴스에만 적용한다. 제안 SQL의 기본 클라이언트 권한은 계속 거부 상태다.

## 호스팅 Supabase 상태

별도 개발 브랜치를 조회했을 때 목록은 비어 있었다. 새 테스트 브랜치 생성 요청은 `Invalid or expired requestState`로 실패했고 재조회에서도 생성된 브랜치는 없었다. 운영 프로젝트에 스키마·사용자·권한 변경을 하지 않았다. 유료 리소스 생성과 관련 승인 없이 임의로 새 계정을 만들거나 기존 운영 프로젝트를 테스트 대상으로 바꾸지 않는다.

`supabase_auth.py`는 **별도 테스트 프로젝트**의 `/auth/v1/user`로 토큰을 검증하는 선택형 서버 어댑터다. 환경변수 미설정 시 네트워크 요청 없이 실패한다. 운영 프로젝트 ref `itljmzmhpviasopdmdfs`, 비공개/서비스 키, 잘못된 프로젝트 ref, 리디렉션을 거부한다. 사용자 요청 본문으로 인증 서버 URL을 바꿀 수 없다.

```text
HS_SUPABASE_TEST_PROJECT_REF=<별도 테스트 프로젝트 ref>
HS_SUPABASE_TEST_PUBLISHABLE_KEY=<그 프로젝트 공개 키>
HS_SUPABASE_TEST_ONLY=yes
```

설정값은 비공개 서버 환경에만 넣는다. 토큰·비밀번호·키를 GitHub나 공개 파일에 넣지 않는다. 실제 호스팅 프로젝트의 테스트 계정 로그인 후 얻은 토큰을 `POST /api/auth/supabase`에 전달하는 API 경계만 제공하며, 일반 회원가입 화면은 기존 로컬 테스트 인증을 사용한다. 이 어댑터 전용 가입/OAuth/비밀번호 복구 화면은 아직 없다.

요청은 `{token, role, nickname, adultConsent:true}`이며 역할은 learner/partner/teacher만 허용한다. 확인된 비익명 사용자와 이메일 확인을 요구한다. 응답의 user_metadata/app_metadata 역할로 로컬 관리자를 부여하지 않는다. 프로젝트+subject로 로컬 테스트 사용자를 연결하며, 이메일 일치만으로 기존 계정에 합치지 않는다. 새 강사도 승인 대기 상태다. 토큰은 DB나 로그에 저장하지 않는다.

**남은 한계:** API 통신은 로컬 전송 모형으로 검사했으며 실제 Supabase 테스트 계정 호출은 실행하지 않았다. 연결 후 발급하는 로컬 세션은 호스팅 계정의 토큰 회수/탈퇴와 자동 동기화되지 않는다. 운영 연동 전 현재 세션 확인·MFA·이메일/계정 복구·Supabase Auth UI·실제 PostgREST/RLS·보안 advisors·Postgres 트랜잭션 어댑터·백업복구를 검증해야 한다. SQLite 수업 데이터를 운영 Supabase로 옮기는 어댑터는 아직 아니다.

## 수업·인증 보안 보완

- 양측 출석 구간의 합집합을 만든 뒤 교집합을 계산한다. 양측이 서로 다른 시간에 각 30분을 채워도 수업 완료를 거부한다. 브라우저 heartbeat는 실제 Jitsi 출석의 증거가 아니다.
- 미결제 예약은 생성 15분 또는 수업 시작 중 먼저 도달하는 시점에 만료된다. API 요청 시 지연 정리하며 다른 예약이 그 자리를 사용할 수 있다. 종료 후 신규 청구는 거부한다.
- 가입 때 추천인이 없더라도 첫 추천 예약에서 하나의 직접 추천인에 고정하며 이후 변경을 차단한다.
- 로그인 실패 횟수는 IP+이메일별로 관리하고 IP 합산 제한도 유지한다. 다른 자기 계정의 정상 로그인으로 타 계정의 실패 제한을 초기화하지 못한다.
- 기존 진행 중 로컬 예약에 과거 출석 합계만 있고 구간 기록이 없다면 새 완료 조건을 자동 충족시키지 않는다. 실제 근거 없이 구간을 소급 생성하지 않는다.

공식 근거: https://supabase.com/docs/reference/javascript/auth-getuser 및 https://supabase.com/docs/guides/api/securing-your-api . 로컬 PostgreSQL 도구의 README와 제공 btree_gist 확장 API를 설치 패키지에서 확인했다. 법률·세무·결제·신원 승인과 실제 PC/스마트폰 통화는 여전히 별도다.
