# 한글쉽지12 4차 실행 보고 — 2026-10-28

## 브랜치 및 통제
- 작업 브랜치: `team12/education-audit-20261028`
- 통합/배포: 없음
- 기존 교육 데이터, 음원, 다른 팀 파일: 변경 없음

## 실제 실행 경로 확보
- 신규 `.github/workflows/team12-education-audit.yml`
- `push` (전용 브랜치, 워크플로/스크립트 변경) 및 `workflow_dispatch` 트리거
- `actions/checkout@v4`로 실제 커밋 체크아웃, `ffmpeg` 설치
- `python3 scripts/team12_audio_inventory.py --root . --output audit/team12-recording-inventory.json`
- `actions/upload-artifact@v4`로 JSON 보존. 워크플로는 `contents: read` 권한으로만 실행.
- GitHub 커넥터의 `fetch_commit_workflow_runs` 확인 결과: 해당 커밋의 PR 연계 실행 0건. 이 API는 PR 트리거 실행만 검색하므로 **전체 push 실행 부재의 증거는 아님**. 실제 Actions 페이지에서 별도 확인 필요.
- 아티팩트는 GitHub Actions 저장소에만 생성되며 Git 브랜치에 자동 커밋되지 않음. 399개 JSON의 Git 추적 저장은 미완료.

## 검사 항목과 결과
| 검사 | 구현 | 실제 실행 |
|---|---|---|
| 399개 글자별 녹음 대본/파일명/상태 JSON | 구현 | 미확인 |
| 파일 존재 | 구현 | 미확인 |
| SHA256 | 구현 | 미확인 |
| FFmpeg 디코딩 | 구현 | 미확인 |
| 상대 경로 유효성 | 구현 | 미확인 |
| 브라우저 자음·모음·글자 클릭 재생 | 기존 브라우저 기록만 있음 | 이번 회차 미실행 |
| 무료 350단원 정답/번역/진도/재진입 | 미구현 | 미실행 |
| 전문 96수업 정답/번역/진도/재진입 | 미구현 | 미실행 |

## 재현 오류/수정
- 이번 회차 새로 재현된 음원 경로·이벤트 오류 없음. 따라서 기존 재생 로직 수정 없음.
- 과거 기록 기준: 399개 중 재생 허용 19, 보류 26, 미확보 354. 이번 회차 검증된 수치 아님.
- `ready_unapproved`는 사람 청취 승인 전 상태. `held`도 승인 전. 합성 음원을 사람 녹음으로 표시하지 않음.
- 감사 스크립트는 `ffmpeg` 실행 파일이 있는 환경을 전제함.

## 브라우저 검사 재현 절차
1. GitHub Actions 또는 동일 SHA를 체크아웃한 로컬 Linux 환경에 Node.js, Chromium/Playwright, Python, FFmpeg 설치.
2. 실제 저장소를 HTTP 서버로 구동. file:// 접근은 fetch 보안 제약으로 부적절.
3. Chromium에서 `hangul-board.html` 열고 콘솔/네트워크 오류를 기록.
4. 자음 이름(예: 기역), 모음(아), 합성 글자(가/거), 보류 글자(다), 미확보 글자(겨) 각각 클릭.
5. 재생 가능 항목에서 Audio.play() 성공, ended 이벤트, 재생 상태 및 URL 200 응답을 확인. 보류/미확보 항목은 재생 차단 및 안내 문구를 확인.
6. 1440px PC/390px 모바일 뷰포트, 새로고침·네트워크 실패 후 재시도 테스트.
7. 검증된 실패만 최소 수정하고 동일 테스트 재실행. 사람 청취 승인은 별도 실제 청취 평가.

## 남은 작업
1. Actions 페이지에서 실제 run URL/SHA/종료 코드 확보.
2. Actions 아티팩트 JSON 검토 후 브랜치에 커밋.
3. 별도 브라우저 실행 테스트 추가 및 실행.
4. 무료 350단원과 전문 96수업의 실제 학습 경로 자동 검사 작성·실행.
5. 실제 오류 발견 시에만 수정.
