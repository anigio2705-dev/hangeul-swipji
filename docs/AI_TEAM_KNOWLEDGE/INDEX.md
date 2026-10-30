# AI Team Knowledge — 공동 사례 색인

대표 2026-10-30 추가 실행 명령 제16~18조에 따른 공동 지식 저장소. 기존 Issue #34, 160개 원장 및 PR/CI 증거는 그대로 보존하며 이 색인에서 연결한다.

## 저장 구조
- [SUCCESS](SUCCESS/README.md): 코드/테스트/독립감사/통합/배포 단계를 구분한 성공 사례
- [FAILURE](FAILURE/README.md): 재현 가능한 실패, 실패한 가설, 차단 조건
- [LESSONS](LESSONS/README.md): 다른 팀에서 재사용 가능한 해결 원칙
- [CROSS_TEAM](CROSS_TEAM/README.md): 적용팀, 원래 사례, 변경 SHA, 실제 재검증 결과

## 사례 필수 항목
사례 ID; 팀; 160개 과제 번호; 현상과 재현; 최초 가설·시도·로그; 근본 원인(확인/추정 구분); 실제 수정 파일·SHA·PR; 테스트 및 독립 검증 URL; 성공 단계(코드/단위 CI/독립 QA/통합/테스트99); 다른 팀 교훈·적용 금지 조건; 협업 요청; 후속 과제.

## 등록·활용 규칙
1. 새 작업 시작 전 색인과 관련 FAILURE/LESSONS/CROSS_TEAM 및 Issue #34를 검색한다.
2. 과거 해법을 적용하면 '그대로 성공 / 수정 후 성공 / 실패 / 적용 불가'로 기록하고 반드시 현재 HEAD SHA의 테스트를 첨부한다.
3. 성공·실패를 실제 증거 없이 승격하지 않는다. 테스트99 성공은 실제 배포 SHA·데이터 보존·실사용 확인이 있어야 한다.
4. 중앙은 새 사례와 관련 팀/과제를 연결한다. 15팀은 반례와 독립 검증을 기록한다.
5. 사례 수, 재사용 수, 재사용 통과 수, 재발 수, 해결 시간, 자동 승계 성공률을 측정하되 형식적 사례 양산을 금한다.

## 기존 증거 연결
- [중앙 접수·실행·교차 협업 Issue #34](https://github.com/anigio2705-dev/hangeul-swipji/issues/34)
- [GitHub Actions](https://github.com/anigio2705-dev/hangeul-swipji/actions)
- [160개 실행원장](../../automation/hq_backlog_160.md)

이 문서의 생성만으로 각 팀이 실제 사례를 제출했거나 자동 검색·재사용 엔진이 구현됐다는 뜻은 아니다.
