# 17차 Team15 비운영 통합 검사 — 실행 상태 기록

## 16차 실패 회귀
- `test_outsider_cannot_list_other_booking`: 기존 기대 HTTP 200 / 실제 401
- `test_student_sees_only_own_booking`: 기존 기대 1건 / 실제 0건
- 11번 최신 수정 HEAD `7782200d58b28a35d3b5c1edb263f45452018863`를 독립/통합 워크플로에 고정.
- 비운영 통합 workflow에서 `python3 -m unittest discover -s team11/phase3 -p 'test_common*.py' -v` 실행하도록 추가. 테스트 원본/기준 변경 없음.

## 실제 수정 커밋
- 독립 회귀 최신 SHA `c19699c80b6793b41f70aa526c47aadf3a8e5af0`
- 비운영 통합 최신 팀 SHA `40e107ea1cedce0a636062756853663c2f82a881`
- Team11 전체 회귀 단계 `d1fc519f9f1c4fe1e534dbf3c59f4fe18e7a64a7`

## 최신 팀 HEAD
- 11 `7782200d58b28a35d3b5c1edb263f45452018863`
- 12 `8ba857591ba6c3ba9d892d5ec9c543c3b25a5939`
- 13 `f6028d934d615f27d733b6fb7b8299ac1befc240`
- 14 `da8933691d27dc50586a8b76a09d93c54fc08754`

## 정직한 검증 상태
- 17차 최신 Actions run ID, job 로그, 성공/실패 건수는 아직 확보되지 않았다. 따라서 Team11 오류 수정 완료, Team15 독립 검사 통과는 **미확인**.
- 기존 Team11 함수↔Team14 모의 원장 테스트와 SQLite 재개방 검사는 workflow에 유지.
- Team12 무료학습→Team13 예약, Team11 실제 세션→Team13 모의 화상방, Team13 인증 이벤트→Team14 원장 단일 서버 통합 10단계는 **미완료**. 각 팀 독립 PASS를 E2E PASS로 간주하지 않는다.
- 운영 서버/main, 실제 금전 이동, 실제 A/V 및 대표 수동 검사는 진행하지 않았다.

## 160개 수행률
- 10차 공식 잠정 기준선 전체 **30.38%**.
- 최신 11~14 항목별 점수와 증거를 완전하게 재취합하지 못해 17차 최신 전체 평균/증가분 **미확정**.
- 21~30은 11번 책임 점수로 1회만 집계. 131~160은 QA 코드 변경만으로 일괄 상향하지 않음.

## 다음 P0
1. 17차 GitHub Actions 실제 실행 결과/실패 스택 수집 후 Team15 검사 코드 결함 수정 또는 Team11에 정확한 실패 계약 전달.
2. 11→13 HTTP 인증·예약 소유권 실제 연결, 13→14 이벤트 provenance/원장 DB 원자성 통합.
3. Team12 학습 진도·강사 예약 실제 HTTP 흐름 결합.
4. 실제 가상 사용자 10단계 통합 자동 검사와 160개 근거 기반 재평가.
