# Team11 18th pass — authenticated per-user free lesson progress API

## Real code changes
- `phase3/schema.sql`: `free_lesson_progress(user_id,stage,lesson,completed_at)`, composite PK, foreign key to users, stage 1–7, lesson 1–50.
- `phase3/server.py`: authenticated `GET /api/free-progress` and `POST /api/free-progress`; role=learner, server-derived user ID from hs3 session; idempotent `INSERT OR IGNORE`; strict int and range checks; never accepts client user ID.
- `phase3/test_common_http_free_progress.py`: four real loopback HTTP tests with isolated temporary SQLite: save/reconnect, duplicate idempotency, account isolation, missing auth/provider role/invalid ranges.
- Commits: schema `e97975cf67881e143a0b1df0aa50ac0a6a1abecd`, server `80cb1641b4e5080d2111eb19301d779264b334c3`, tests `ee4b442fd658759cd4a67bee94b5ce10626478f4`.
- Previous 96 tests retained; **100 authored test methods expected**. No test execution or CI run ID verified in this session. No green status claimed.

## Team12 handoff
- POST `/api/free-progress` with JSON `{"stage":1,"lesson":1}`, cookie `hs3` from actual login. Response `{"ok":true,"stage":1,"lesson":1}`. Stage 1–7, lesson 1–50; 350 total.
- GET `/api/free-progress` with cookie returns `{"completed":[{"stage":1,"lesson":1,"completedAt":...}],"count":1}`.
- Client must not send or infer user ID; server derives from cookie session. Existing 12-team resume UI remains separate until wired on integration branch.
- Existing `GET /api/learning` placement/diagnostics API preserved. No quiz scores are stored in new progress table; this API tracks lesson completion only.

## Team13/15 handoff
- Booking and attendance checks remain from earlier passes; same server session and SQLite connection used for free-progress.
- Team15 should combine current branch with Team12/13/14 on nonproduction branch and execute actual HTTP flow. No claim of full 12-step integration or successful merge.

## Progress
- Previous provisional Team11 mean 45.55%. #37 60 -> 70% provisional for new real server progress persistence API (requires CI and Team12 integration). Remaining 39 items unchanged. New mean **45.80%** (+0.25 pp). Team15 must independently verify original item wording; this is not official.
- Baseline per-item file: `docs/team11/TENTH_PASS_PROGRESS_1_40_20261028.md`. Overrides: #29=60, #33=87, #36=75, #37=70; others unchanged.

## Open
- CI execution evidence, HTTP test success, server-process restart, Team12 UI integration.
- Whole-platform nonproduction merge and Team13/14 event-to-ledger flow.
- No main, production server, live money, real audio/video, or instant matching changes.
