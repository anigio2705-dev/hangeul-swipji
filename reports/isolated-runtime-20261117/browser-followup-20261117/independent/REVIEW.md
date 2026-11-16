# 독립 검토 — 한정된 실제 UI·저장·계정 분리 수락

판정: **ACCEPT_SCOPED_FIXTURE_REPAIR_STATEMENT_UI_STORAGE_AND_ACCOUNT_ISOLATION**.

검토한 최종 제품 변경은 phase3/app.js의 진술 조회/본인 추가 UI 연결이다. 실제 실행/검토한 app.js SHA256은 `1254ad0d1698541a8a67a6ad287c2d8c6425108fcab20d062dc7d040fef5ba24`다. 제품 기준 원본은 `94a40b84c4c5665b5964b47f128b9472cfdae6eb`이며 초기 PR345의 검사 보강과 그 후 실제 화면에서 발견한 진술 입력 부재 수리는 다른 변경이다.

기존 검사5파일 변경을 원본과 대조했다. 최소 DB에 누락됐던 observation/audit 스키마, 최신 API 모형, 상대방 진술 선행 조건, 동일 환불 요청의 멱등 응답, DOM 유틸리티 대역을 보강한 것이다. 기존 교육/권한/UTC/원장 불변 단언을 삭제하거나 제품 권한을 완화한 수정은 발견하지 않았다. 부모의 브라우저 fixture 보강도 시간 입력 중복에 대한 form scope, 기기보다 참여자 프로필 시간대 우선, 학생 정답/교사지도 비공개의 기존 계약을 반영한다.

독립 작성 HTTP/SQLite 사례4개를 실제 임시 서버에서 실행하여 통과했다. 다른 계정·관리자의 상대방 진술 위조 거부, 동일 환불 요청 ID의 금액 변경 거부와 원장 불변, 로그인 사용자별 진단/프로필 보존, 로그아웃된 세션의 서버 재생성 후 거부를 확인했다. 기존92개와 중복 합산하지 않는다.

별도 실제 Chromium 시나리오 두 개도 실행했다. 첫 시나리오는 두 개의 독립 브라우저 계정 가입, 한 계정의 실제 프로필 저장·새로고침 보존, 다른 계정 불변, 실제 세션 API 재조회와 read-only SQLite 직접 대조, 390px 문서 가로 넘침 부재의6개 확인이다. 데스크톱·모바일 스크린샷을 직접 열어 확인했다. 실제 휴대전화 검사는 아니다.

두 번째는 진술 UI 수정에 대한6개 확인이다. 비참여자 실제GET403, 교사가 원신고를 읽고 본인 진술을 화면에서 저장, 새로고침 후 보존 및 script 문자열의 텍스트 처리, 관리자 화면의 읽기 전용(입력·저장 버튼 없음), 관리자 직접POST403, 실제 로그아웃 도중 지연시킨 GET응답을 반환해도 진술 dialog가 열리지 않음을 확인했다. 두 브라우저 시나리오의 pageerror는0개다. API로 준비한 가상 예약/신고를 사용했으며 해당 준비가 가입/예약 UI 실증이라는 뜻은 아니다.

차단 결함은 이 검토 범위에서 발견하지 않았다. 부모가 실행한 기존 전체 화면 시나리오를 이 검토자가 독립적으로 전부 재실행했다고 주장하지 않는다. 전체 제품 무결점, 실제 교육/음성 품질, 실제 기기·통화, 운영 Supabase/결제,24시간 시험 통과는 이 판정 범위에 없다. 생성한 서버·브라우저는 종료하고 임시 DB를 정리했다. 운영/기존24시간 실행/GitHub 변경·모델 호출은0이다.

재현(정확한 제품 checkout을 지정):

```sh
HS_REVIEW_SOURCE=/absolute/path/to/repo python test_independent_boundaries.py
HS_REVIEW_SOURCE=/absolute/path/to/repo node browser_independent.cjs
HS_REVIEW_SOURCE=/absolute/path/to/repo node browser_dispute_independent.cjs
```

Node 시나리오는 대상 저장소의 phase3/node_modules/playwright를 사용한다. 실행 원문·결과·정확한 코드/증거 해시는 INDEPENDENT_TESTS.log, INDEPENDENT_BROWSER.log, INDEPENDENT_DISPUTE_BROWSER.log, REVIEW.json, MANIFEST.json에 보존한다. 검토자는 제품/검사 원본을 수정하지 않았고 독립 산출물만 작성했다.
