# 한글쉽지 통합 교육 플랫폼 · 테스트 백엔드

현재 통합 브랜치는 **기존 홈페이지 `/`를 유일한 메인으로** 사용합니다. 강사 수업은 홈페이지 내부의 `#teaching-platform` 영역이며 별도 브랜드·히어로·홈페이지를 만들지 않습니다. `/phase3/index.html`, `/teaching-platform.html`, `/free/`는 이전 링크 호환을 위한 이동 경로입니다.

```bash
python3 phase3/server.py
# http://127.0.0.1:8765/ 에서 기존 홈과 통합 수업 화면 확인
```

4단계·96수업은 기간이나 모집 인원 제한이 없는 교육 기준안입니다. 기존 독립12단원·36문항을 보존하고 새12단원·36문항을 별도 파일로 추가했습니다. 24수업은 열람·예약 가능하며 72수업은 미제작으로 표시합니다. `curriculum-96.json`은 단계·순서·진단·루브릭, `content-expansion.json`은 신규 학생용/강사용 교재입니다.

학습자는 무료 진단 요약을 자발적으로 저장하고, 사전 내용 확인→예약→수업→사후 내용 확인과 강사의 관찰→과제·피드백→다음 교재를 이어갑니다. 자동 내용 확인은 발음·실제 대화 능력을 평가하지 않습니다. 강사/파트너는 가입·프로필·가능시간 등록을 할 수 있고 검토 전에는 공개 검색·예약이 차단됩니다. 공개 검색에는 목적·가격·언어·수준·시간 조건과 페이지 이동이 있습니다. 참여 인원 상한을 두지 않았지만 동시 대규모 운영을 검증한 상태는 아닙니다.

신규 학습 기록은 격리 SQLite의 `learning_placements`, `learning_checks`에만 저장합니다. 운영 Supabase에는 적용하지 않습니다. 실제 서버·계정·결제·영상·개인정보 운영 검증과 승인 없이 운영 배포하지 않습니다. 핵심 메뉴는 지정8언어로 제공하며 전문 교재의 학습 언어는 한국어, 일부 안내는 영어입니다. 모든 설명·오류·수행평가를8언어로 완역한 상태는 아닙니다.

아래는 기존3차 개발의 실행·정책·검사 경계 기록입니다. 교재 수와 홈페이지 진입 경로는 위 통합 설명이 최신입니다.

---

# 한글쉽지 3차 · 격리된 테스트 플랫폼

**운영 서비스 완성본이 아닌, 실제 실행 가능한 다중 사용자 로컬 테스트 시스템입니다.** 모든 거래·정산·추천은 TEST 원장입니다. 현금·카드번호·신분증을 입력하지 마세요. 기존 무료 350단원·600읽기·메인·운영 Supabase는 수정하지 않습니다.

- 브랜치: `phase3/global-teaching-platform-20261026`
- 시작점: `fb709fcb8108fc8d0ccdb6386a6d95d2e074035a`
- main 병합 / GitHub Pages 배포 / 운영 DB 적용: 하지 않음
- Learn → Speak → Teach → Earn의 수업 흐름을 별도 서버에서 검증

## 실행

Python 3.12 이상, 외부 패키지 없이 실행합니다. 정확한 CLI는 `python phase3/server.py --help`에서 확인합니다.

```bash
python phase3/server.py --help
python -m unittest discover -s phase3 -p 'test_*.py' -v
python phase3/server.py
```

서버가 출력한 localhost 주소를 엽니다. GitHub Pages에서 HTML만 열면 API 서버는 실행되지 않습니다. 운영 호스트 배포가 별도로 필요합니다. 기본 서버는 로컬 접근만 허용합니다.

실제 이메일 대신 테스트용 주소를 사용해 학습자, 회화 파트너, 전문 강사를 별도 브라우저 세션에서 생성합니다. 운영자 생성은 CLI에서만 하며 웹 회원가입으로 관리자 역할을 받을 수 없습니다. 계정 승인 표시는 이 로컬 테스트 안에서만 유효합니다. 실명·자격·연령 검증 사업자와 연결된 상태가 아닙니다.

## 검증할 흐름

1. 강사/파트너 가입 → 프로필 → 운영자 테스트 승인 → 가능 시간 등록
2. 학습자 가입 → 필터 검색 → 시간·단원 선택 → 예약 → 테스트 결제
3. 두 참여자가 같은 예약의 단원과 방을 열기
4. 출석 기록·양측 완료 확인·운영자 증빙 검토 → 테스트 완료
5. 숙제·피드백·후기·재예약, 직접 추천 연결
6. 분쟁 → 조사 사유 → 환불/기각/재수업 처리 → 정산·보상 원장 추적

화상방 링크 발급과 실제 두 기기의 음성·영상 연결은 별개입니다. 공개 Jitsi 시험방은 링크를 아는 제3자의 입장을 차단하는 상용 인증 체계를 제공하지 않습니다. 운영 전 인증된 전용 화상 서버와 검증 가능한 출석 이벤트가 필요합니다. 브라우저 체류시간과 수동 증빙은 실제 강의 품질을 증명하지 않습니다.

## 운영 전 미충족 조건

- Supabase Auth 기반 계정 연결, 이메일 검증/비밀번호 복구/세션 회수, 실제 RLS 실행 검증
- 격리된 PostgreSQL에서 DDL·동시 예약·RLS·복구 검증 후 운영 이전 계획
- PG의 마켓플레이스 심사와 테스트 자격증명, 서명 webhook, 환불·차지백 대사
- 전문 자격/신원/성인 확인, 국가별 참여 제한, 미성년 보호자 동의와 안전 운영
- Jitsi JWT/서버 출석 증빙, 실제 PC·스마트폰 간 통화 검사
- 외부 보안 점검, 부하/침해/백업·복구 테스트, 운영 모니터링
- 변호사·세무사·PG의 계약/결제/정산/직접 추천 보상 검토
- 전문 강사 검수와 실제 학습자 파일럿; 12개 독립 시범 단원의 확대

현재 로컬 인증을 운영 Supabase 인증으로 오인하지 마세요. `supabase-preview.sql`은 **적용하지 않은 설계안**이며 Python 서버는 그 SQL을 사용하지 않습니다. 기존 운영 회원·거래를 이 테스트 서버로 복사하지 않습니다.

## 문서

- [구현·검사 현황](STATUS.md)
- [교재 범위](CURRICULUM.md)
- [참고 교육 프로그램 조사](REFERENCE-RESEARCH.md)
- [법률·세무 검토](LEGAL-REVIEW.md)
- [약관·정책 초안](POLICIES-DRAFT.md)
- [Supabase 운영 연동 과제](SUPABASE-INTEGRATION.md)

정책 초안은 서비스 동의문이나 법률 자문으로 확정된 문서가 아닙니다. 테스트 데이터도 개인정보가 될 수 있으므로 로컬 테스트만 수행하고 필요가 끝나면 관리 절차에 따라 삭제합니다.


## 관리자 생성과 브라우저 재검사

```bash
# 실제 개인 비밀번호 대신 이 로컬 시험 전용의 새 비밀번호를 사용합니다.
read -s HS_PHASE3_ADMIN_PASSWORD
export HS_PHASE3_ADMIN_PASSWORD
python phase3/server.py --create-admin admin@example.test
unset HS_PHASE3_ADMIN_PASSWORD
python phase3/server.py --port 8765
```

브라우저 검사는 별도 임시 DB와 서버를 자동 생성하고, 종료 시 자기 임시 데이터만 정리합니다. 운영 DB에 접근하지 않습니다. 도구 의존성은 버전과 lockfile을 고정했습니다.

```bash
npm ci --prefix phase3 --ignore-scripts
./phase3/node_modules/.bin/playwright install chromium
node phase3/browser-test.cjs
```

CI에는 한글 표시 확인을 위한 Noto CJK 글꼴을 설치합니다. UI는 시스템 한글 글꼴을 사용하며 외부 폰트 CDN으로 개인정보를 전송하지 않습니다. 모바일 확인은 390px Chromium 에뮬레이션이며 실제 Android/iPhone 장치 검사와 다릅니다.

## 이번 보강 검증

```bash
python -m unittest discover -s phase3 -p 'test_*.py' -v
npm ci --prefix phase3 --ignore-scripts
node phase3/postgres-test.cjs
node phase3/browser-test.cjs
```

PostgreSQL 검사는 로컬 PGlite 엔진과 Auth 모형을 사용합니다. 현재 엔진은 PostgreSQL18이며 기존 호스팅 프로젝트 PostgreSQL17과 동일한 배포 환경이 아닙니다. 호스팅 Supabase 로그인·JWT·PostgREST·네트워크 정책 검증으로 표시하지 않습니다. 자세한 경계는 [AUTH-TESTING.md](AUTH-TESTING.md), PG 테스트 계약과 실제 계정 미검증 범위는 [PAYMENTS.md](PAYMENTS.md)에 있습니다.

브라우저 검사에 사용하는 `browser_server.py`는 일회성 테스트 DB 및 파일 기반 모의 시계 전용 실행기입니다. 운영 서버에는 시간을 바꾸는 HTTP API가 없습니다. 예약→30분 겹친 출석→양측 확인→관리자 증빙→완료→후기→모의 정산→모의 환불 흐름을 짧은 시간에 재현하되, 실제 화상통화나 강의 제공을 입증하지 않습니다.
