# 한글쉽지 1·2·3번 실서비스 연결 절차

현재 GitHub Pages는 기존 Supabase 프로젝트 `itljmzmhpviasopdmdfs`에 연결되어 있습니다. 회원 인증, 프로필, 대기·매칭용 DB 함수와 Jitsi 시험방을 사용하는 시범 서비스입니다. 별도 프로젝트를 다시 만들지 마세요.

## 1. Supabase 연결 (운영자 1회)
1. https://supabase.com 에 로그인하여 기존 `hangeul-swipji` 프로젝트를 선택합니다.
2. 먼저 `supabase-speaking-audit.sql`로 실제 구조를 확인하고 저장소와 비교합니다. `supabase-speaking.sql`은 전체 구성 기준이며, 운영 중에는 검토된 차이만 적용합니다.
3. Authentication > URL Configuration에서 Site URL을 `https://anigio2705-dev.github.io/hangeul-swipji/` 로 지정하고 Redirect URLs에 `https://anigio2705-dev.github.io/hangeul-swipji/**` 를 추가합니다.
4. Authentication > Providers에서 Email 인증 정책을 확인합니다.
5. Project Settings > API의 **Project URL과 anon/publishable key만** `speaking-config.js`에 입력합니다. **service_role 또는 secret 키는 절대로 공개 저장소에 넣지 않습니다.**
6. 페이지 `speaking-platform.html`을 열어 서로 다른 이메일로 학습자와 한국인 파트너를 가입시킵니다.

## 2. 파트너 승인
보안을 위해 파트너가 가입하자마자 다른 사람에게 노출되지는 않습니다. 운영자는 Supabase Table Editor에서 `profiles`의 해당 회원 `approved`를 true로 바꿉니다. 승인된 파트너만 대기할 수 있습니다.

## 3. 2계정 검증
1. 한국인 계정에서 프로필을 '한국인 파트너'로 저장하고 승인 후 온라인 대기를 시작합니다.
2. 외국인 학습자 계정에서 '한국인 찾기'를 눌러 대화 요청을 보냅니다.
3. 한국인 계정에서 요청을 수락합니다.
4. 두 계정에서 화상방에 입장하고 카메라·마이크 권한을 허용합니다.
5. 대화를 종료하고 재매칭이 되는지 확인합니다.

## 운영 전 필수 보완
- 현재 화상통화는 Jitsi 공개 시험 인프라를 사용하며, 방 URL을 아는 제3자 접속을 기술적으로 차단하지 못합니다. 정식 공개 서비스에 앞서 인증 토큰 기반 전용 화상 인프라가 필요합니다.
- 파트너 신원 확인, 신고·차단, 예약, 노쇼 방지, 개인정보 처리방침 및 이용약관, 악용 방지, 운영자 관리 화면이 아직 필요합니다.
- 현재 대기 갱신은 브라우저가 열려 있을 때만 동작하며, 백그라운드 탭의 갱신은 지연될 수 있습니다.
- Google Translate를 통한 번역은 서비스 언어별 완전한 현지화가 아닙니다.
- 공개 출시 전 보안 및 2인 실통화 테스트를 통과해야 합니다.

## 현 상태
1. 회원가입·개인 공간: 기존 Supabase 연결 설정됨. 최초 프로필은 INSERT, 기존 프로필은 허용된 네 필드만 UPDATE합니다.
2. 실시간 대기·매칭: 승인된 파트너의 대기 및 요청·수락·거절·종료 함수가 실제 DB에 존재합니다.
3. 1:1 화상: Jitsi 시험방 연결 구현, 전용 인증 서버 미구축
4. 공통 교재: 별도 개발

## DB와 파일 동기화 기준
- `respond_match`의 난수 생성은 `extensions.gen_random_bytes(18)`로 명시합니다. 빈 `search_path`에서 경로 없는 호출로 되돌리지 마세요.
- 일반 회원은 자기 프로필의 `nickname`, `role`, `level`, `topic`만 수정합니다. `approved`, `is_online`, `last_seen`, `id`, `created_at`은 직접 수정하지 못합니다.
- 프로필 저장 오류를 해결하려고 테이블 전체 UPDATE 권한을 주지 마세요. 기존 프로필 저장은 ID를 UPDATE하는 upsert 대신 `.update(fields).eq('id', user.id)`를 사용합니다.
- 일반 회원과 비로그인 사용자에게 테이블 TRUNCATE 권한을 부여하지 마세요.
- `supabase-speaking-audit.sql`은 구조·권한만 읽습니다. 실제 회원이나 매칭 내용은 출력하지 않습니다.
- DB 기능 검증과 두 실제 기기 간 카메라·마이크 통화 검증은 별개입니다.
