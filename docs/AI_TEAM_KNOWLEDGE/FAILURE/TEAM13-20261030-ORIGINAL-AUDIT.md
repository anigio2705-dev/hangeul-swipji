# TEAM13-20261030-ORIGINAL-AUDIT — 통합 원본 보존 감사 실패

- 팀: 13 플랫폼 / 연계: 12 교육, 15 독립 감사, 중앙 총괄
- 160개 과제 번호: 중앙 원장 매핑 확인 전 미확정
- 브랜치: integration/team13-instant-entry-20261030 / PR #86
- 현상: 13팀 전용 회귀 성공에도 전체 통합 검사의 scripts/audit-professional-96.py가 HTML 원본 변경을 검출하여 실패
- 재현: [전체 통합 CI #40973767510](https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40973767510)
- 성공 범위: [13팀 회귀 #40973761662](https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40973761662) PASS; [Phase3 #40973767394](https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40973767394) PASS. **전체 통합/테스트99 배포 성공 아님.**
- 관찰: intro.html, beginner1/2.html, intermediate1/2.html, advanced1/2.html, index.html 총 8개 파일 변경 검출
- 원인 가설 A: 교육 HTML 7개는 13팀 격리 작업 전 통합 베이스에서 유래; index.html은 즉시 자동매칭 진입 CTA 변경. 각 파일 변경의 승인·기준선 적합성은 별도 검증 필요
- 최초 시도: 충돌이 큰 기존 PR #84 대신 통합 베이스 기반 격리 PR #86으로 최소 변경 분리; ubuntu-24.04 및 fetch-depth 0으로 실행 환경 오류 수정
- 실제 제품·검증 HEAD: 2c088c24ebb613e3c212ca1eca0b3b85b56646b4 (당시 확인 기준)
- 해결안: 12팀이 7개 교육 HTML의 원본 복원 또는 승인된 파일별 digest를 확인; 15팀이 원본 보호 규칙과 변경 후 전체 CI를 독립 검증; 13팀은 즉시 매칭 CTA 보존 및 브라우저 회귀 수행
- 적용 금지: 원본 감사 전체 삭제, HTML 전체 일괄 예외, 단위 테스트 PASS를 통합·배포 성공으로 표시
- 협력 요청: [Issue #103](https://github.com/anigio2705-dev/hangeul-swipji/issues/103), [중앙 접수](https://github.com/anigio2705-dev/hangeul-swipji/issues/34#issuecomment-6511241793)
- 다음 작업: 최신 통합 HEAD에서 실패가 아직 유효한지 재현한 뒤 12·15팀과 수정·독립 검증. 과거 로그만으로 현재 실패 지속을 단정하지 않는다.
