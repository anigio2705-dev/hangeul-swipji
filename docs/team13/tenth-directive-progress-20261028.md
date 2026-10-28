# Team13 — 10th directive item-by-item development progress (2026-10-28)

Original numbering: 21–30 (collaboration with Team11) and 71–100 (Team13 primary); 40 entries. Source: docs/platform-execution-backlog-20261027/docs/PLATFORM_EXECUTION_BACKLOG.md. Progress is a conservative **development estimate**, NOT verified completion. Do not add Team13's ten shared items twice to the 160-item HQ mean.

Baseline verified before latest changes: https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40613496099 — 88 Python tests PASS, 13 browser PASS (mocked video only).
New implementation commits: d7c93f007d4df20bfa5e31cd162da213344fe807 (booking lifecycle read model); 3a26efb508e83ad303a64b2514f6eae039037a0d (regression tests). New run verified: https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40616132674 — Python 90/90 OK, browser 13/13 PASS, no failures. This remains isolated automated validation; no item claimed fully complete.

Scoring: 0 not implemented; 20 design/partial scaffolding; 40 partial working implementation; 60 core feature implemented but integration/exceptions missing; 80 connected and validation pending; 90 automated pass but real-world checks pending; 100 only after full original acceptance. Scores can use intermediate 10-point increments. A code file or test alone does not justify 100.

| No. | Original feature | Implemented evidence | Missing / next action | Score | Cross-team status |
|---:|---|---|---|---:|---|
|21|홈의 화상 버튼이 테스트 환경의 올바른 예약·수업 화면으로 연결되게 한다.|Home CTA test passes, but full public route not verified|Implement missing lifecycle or integration and run failure-path tests|60%|Team13 isolated or pending|
|22|회화 파트너·강사와 학습자가 같은 예약의 같은 방으로 들어가게 한다.|Mocked same-room test and booking route|Authorize reserved-room join on server; real devices HOLD|70%|Team11/14 contract not integrated|
|23|Jitsi 진행자 인증을 수업 계정·테스트 입장 인증과 구분하고 강사의 입장 절차를 완성한다.|Jitsi provider identity enforcement not demonstrated|HQ/vendor/human verification required|20%|Team11/14 contract not integrated|
|24|카메라·마이크 미리보기와 권한 거부·장치 없음·점유 오류 안내를 실제 브라우저에서 검사한다.|Actual camera/mic error states not exhaustively tested|Implement missing lifecycle or integration and run failure-path tests|30%|Team13 isolated or pending|
|25|개발 측에서 별도 테스트 기기·계정으로 양방향 영상과 음성을 먼저 검사한다.|Physical two-device audio/video not run|HQ/vendor/human verification required|0%|Team13 isolated or pending|
|26|실제 PC와 휴대폰에서 같은 방 입장·영상·음성을 검사하고 마지막 현장 확인만 대표와 진행한다.|PC/phone real video/audio and owner final verification|HQ/vendor/human verification required|0%|Team13 isolated or pending|
|27|음소거·카메라 끄기·장치 전환·종료·재접속을 검사한다.|Device switching and reconnect not comprehensively tested|Implement missing lifecycle or integration and run failure-path tests|40%|Team13 isolated or pending|
|28|강사 지각·학생 대기·연결 끊김·통화 제공업체 오류에서 복귀 경로를 마련한다.|Waiting/expiry tested; provider outage/late arrival gaps|Implement missing lifecycle or integration and run failure-path tests|40%|Team13 isolated or pending|
|29|예약 참여자 외의 입장·링크 공유·방 접근 위험을 점검하고 필요한 통제를 적용한다.|API ownership tested; leaked Jitsi link external access risk|Implement missing lifecycle or integration and run failure-path tests|40%|Team11/14 contract not integrated|
|30|카메라 미리보기·방 입장·실제 통화·수업 이행 기록을 구분해 증거와 함께 저장한다.|Mocked vs real evidence distinction documented; full session evidence absent|Implement missing lifecycle or integration and run failure-path tests|30%|Team13 isolated or pending|
|71|회화 파트너·전문 강사의 신청→프로필→검토→공개→예약 흐름을 완성한다.|Teaching application-to-publication flow not integrated|Implement missing lifecycle or integration and run failure-path tests|30%|Team11/14 contract not integrated|
|72|가르칠 수 있는 언어·소개·경력·분야·가격·가능 시간을 등록하게 한다.|Legacy teacher profile fields exist; full editing verification missing|Implement missing lifecycle or integration and run failure-path tests|40%|Team13 isolated or pending|
|73|일반 파트너에게 전문 자격이 있는 것처럼 표시하지 않고 확인된 자격만 구분 표시한다.|Common teaching-profile approval mapping not integrated|Implement missing lifecycle or integration and run failure-path tests|30%|Team11/14 contract not integrated|
|74|강사가 단과와 월 과정의 수업 조건·교재·과제를 안내하게 한다.|Single/monthly lesson condition UI missing evidence|Implement missing lifecycle or integration and run failure-path tests|20%|Team13 isolated or pending|
|75|강사에게 화상 접속·교재 사용·출석·과제·평가·취소 처리 안내를 제공한다.|Teacher operating guide not fully verified|Implement missing lifecycle or integration and run failure-path tests|30%|Team13 isolated or pending|
|76|강사 일정 등록·수정·휴무·기존 예약 충돌 처리를 구현한다.|Legacy slots exist; leave/change/conflict lifecycle not verified|Implement missing lifecycle or integration and run failure-path tests|40%|Team13 isolated or pending|
|77|신규 신청과 모집 규모를 임의의 소수 인원으로 제한하지 않고 목록을 나누어 처리한다.|No verified unbounded/paginated recruitment|Implement missing lifecycle or integration and run failure-path tests|20%|Team13 isolated or pending|
|78|승인·반려·보완 요청에 이유와 재검토 절차를 남긴다.|Approval rejection/review reasons not integrated|Implement missing lifecycle or integration and run failure-path tests|20%|Team11/14 contract not integrated|
|79|강사가 예약·수업 완료·정산 예정·차감 이유를 한곳에서 확인하게 한다.|Teacher dashboard full booking/completion/accrual integration absent|Implement missing lifecycle or integration and run failure-path tests|30%|Team13 isolated or pending|
|80|강사 중단·탈퇴 때 남은 예약의 취소·이관·환불을 처리하게 한다.|Provider exit with bookings unresolved|Implement missing lifecycle or integration and run failure-path tests|10%|Team13 isolated or pending|
|81|학습자가 목적·현재 수준·편한 언어·시간대·예산을 선택하게 한다.|Learner preference selection not integrated|Implement missing lifecycle or integration and run failure-path tests|20%|Team13 isolated or pending|
|82|조건에 맞는 회화 파트너와 전문 강사를 구분해 검색하게 한다.|Provider search exists in legacy code; multi-criteria integration unverified|Implement missing lifecycle or integration and run failure-path tests|40%|Team13 isolated or pending|
|83|검색 결과에 가격·가능 시간·소개·확인된 경력·후기를 명확하게 보여준다.|Result detail/verified credentials not fully verified|Implement missing lifecycle or integration and run failure-path tests|30%|Team13 isolated or pending|
|84|시간을 학습자와 강사의 현지 시간대로 표시하고 시차·서머타임 오류를 검사한다.|DST/timezone edge testing missing|Implement missing lifecycle or integration and run failure-path tests|20%|Team13 isolated or pending|
|85|처음 배우는 사람에게 적절한 수업·파트너를 고르는 안내를 제공한다.|Beginner recommendation guidance missing evidence|Implement missing lifecycle or integration and run failure-path tests|20%|Team13 isolated or pending|
|86|강사 선택 전에 무료·유료 범위와 한 수업에서 받는 내용을 보여준다.|Free/paid scope and lesson preview unverified|Implement missing lifecycle or integration and run failure-path tests|20%|Team13 isolated or pending|
|87|조건에 맞는 강사가 없을 때 시간·언어 조건 변경과 알림 신청 경로를 제공한다.|No-match fallback notification not integrated|Implement missing lifecycle or integration and run failure-path tests|10%|Team13 isolated or pending|
|88|문의·신고 기능과 연락처 노출 범위·차단 정책을 마련한다.|Inquiry/report/privacy/block policy incomplete|Implement missing lifecycle or integration and run failure-path tests|10%|Team13 isolated or pending|
|89|매칭 결과를 특정 강사에 부당하게 몰아주지 않도록 정렬 기준을 정한다.|Ranking fairness policy needs HQ decision|HQ/vendor/human verification required|20%|Team13 isolated or pending|
|90|무료 학습 기록 요약을 본인 동의하에 선택한 강사에게 전달하게 한다.|Consent and scoped sharing policy needs HQ decision|HQ/vendor/human verification required|10%|Team11/14 contract not integrated|
|91|단과·월 과정의 수업 횟수·길이·유효 기간·가격·예약 방식을 확정한다.|One-off/monthly commercial terms need HQ/owner approval|HQ/vendor/human verification required|20%|Team11/14 contract not integrated|
|92|예약 전에 강사·일정·교재·금액·취소 조건을 한 화면에서 확인하게 한다.|Pre-booking confirmation screen not verified|Implement missing lifecycle or integration and run failure-path tests|30%|Team13 isolated or pending|
|93|동시 예약·중복 클릭으로 한 시간대가 중복 판매되지 않게 한다.|Legacy slot uniqueness and concurrency checks|Cross-team integration and actual service verification|70%|Team11/14 contract not integrated|
|94|월 결제 내역과 개별 수업을 연결하고 완료·잔여·취소 횟수를 정확히 계산한다.|Booking snapshot with lessonState; pure monthly event envelope|Persist monthly sessions and link to Team14 durable consumer|40%|Team11/14 contract not integrated|
|95|반복 수업의 시간 변경·공휴일·강사 휴무·학생 연기를 처리한다.|Recurring reschedule/holiday handling incomplete|Implement missing lifecycle or integration and run failure-path tests|10%|Team13 isolated or pending|
|96|예약 확인·수업 전 알림·일정 변경 알림을 구현한다.|Booking notifications unverified|Implement missing lifecycle or integration and run failure-path tests|20%|Team13 isolated or pending|
|97|수업 화면에 교재·과제·화상·진도·남은 시간을 연결한다.|Booking lesson/unit snapshot exists; full screen flow unverified|Implement missing lifecycle or integration and run failure-path tests|40%|Team13 isolated or pending|
|98|출석·지각·중도 종료를 기록하되 브라우저 타이머만으로 실제 이행을 확정하지 않는다.|Attendance records exist; real lesson delivery not proven|Implement missing lifecycle or integration and run failure-path tests|40%|Team11/14 contract not integrated|
|99|과제 제출·강사 피드백·수업 결과·다음 수업·재예약을 연결한다.|Homework/feedback endpoints exist; full next-booking flow unverified|Implement missing lifecycle or integration and run failure-path tests|30%|Team13 isolated or pending|
|100|월 과정 도중 강사 변경·수강 중단 시 이미 한 수업과 미이행 수업을 구분한다.|Mid-month teacher transfer/cancellation lifecycle incomplete|Implement missing lifecycle or integration and run failure-path tests|10%|Team11/14 contract not integrated|

Team13 40-item mean: **27.8%** (sum 1110 / 40). Primary 71–100 mean: **26.0%**. Collaborative 21–30 mean: **33.0%**. These estimates do not substitute for Team15 independent review or the unique 160-item mean.

## Cross-team requests to HQ
- Team11: stable authenticated user/teaching-profile ID, scoped approval and revocation, reserved-room authorization ownership. Current users.role/users.approved are legacy-only.
- Team12: authenticated learning-progress-to-search navigation contract; no cross-branch integration claimed.
- Team14: durable idempotent lesson.completed/cancelled consumer using bookingId/eventId/monthId/lessonIndex, no live settlement.
- Team15: independent branch integration and security tests, review conservative scores.

## HOLD
Real PC/phone bidirectional video/audio, provider-side Jitsi room access enforcement, production DB/deployment, financial policy and real money. Do not infer that an API hiding roomUrl revokes a previously shared external Jitsi URL.
