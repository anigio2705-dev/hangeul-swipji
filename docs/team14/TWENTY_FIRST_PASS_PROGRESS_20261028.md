# Team14 21차 — 실제 예약 가격과 정산 원장 검증 오류 수정

## 수정 파일 / 커밋
- `phase3/team14_team11_db_adapter.py`: 서버 예약 테이블의 `price`를 조회하고 `booking_price_krw`로 제공. `2aa6c4c19e9f5b4e4418be4ecb69bebdbf48a06e`
- `phase3/team14_server_db_wiring.py`: 정산 원장의 수업 금액과 서버 예약 금액이 다르면 정산 거부. `b0e09b26fdbb210c8a0c06a2e807f940c0ca2260`
- `phase3/test_team14_team11_db_adapter.py`: 실제 서버 예약 DB 구조에 맞춰 `price` 컬럼 테스트 fixture 보강. `58541588c514d846d1145c38ea4c5e9a95ab4773`
- `phase3/test_team14_server_db_wiring.py`: 금액 불일치 시 모의 정산 원장 무기록 회귀 테스트 추가. `975a8d9481175e155b4320c107a118c18b92c901`
- CI workflow 기존 테스트 자동 탐색 경로 유지. 신규 1개 포함 약 138개 테스트 대상. 실제 PASS 수는 GitHub Actions 실행 결과로 확인해야 함.

## 검사와 연결 상태
- 20차 Team14 최신 CI 성공은 총괄본부 확인 기준.
- **21차 최신 수정 커밋에 대한 GitHub Actions 성공 로그/실행 번호 미확보**.
- Team11 예약 SQLite 조회→Team14 모의 정산 코드 연결: 구현, 금액 불일치 차단 추가.
- Team13 실제 영구 이벤트 저장소→Team14: **미연결**. 기존 신뢰된 서버 이벤트 조회 콜백 계약만 존재. 임의 콜백을 인증 증거로 간주해서는 안 됨.
- Team15 전체 HTTP/DB E2E: **미확인**.
- 실결제·실송금·운영 배포 없음. 즉시 자동 매칭 및 교육 콘텐츠 수정 없음.

## 수행률
101~130번 기존 잠정 **32.67% 유지**. 이번 작업은 기존 연결의 금액 검증 오류 수정으로, CI 및 실제 Team13 연결 확인 없이 수행률을 추가 상향하지 않음.

## 미완료
1. Team13의 인증된 서버 이벤트 저장소에서 실제 조회/전달 함수 연결.
2. Team15 단일 비운영 서버 예약→수업 완료→정산→환불→재시작 E2E 검증.
3. 별도 SQLite 정산/소개 보상 DB의 중간 장애 시 원자성 또는 영구 복구 상태 관리.
4. 21차 최신 GitHub Actions 실행 성공 여부 확인 및 실패 시 수정.
