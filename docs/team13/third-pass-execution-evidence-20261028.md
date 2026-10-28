# Team13 third-pass execution evidence — 2026-10-28

## Source and branch
Repository: anigio2705-dev/hangeul-swipji
Branch: team13/platform-bfcache-reconnect-20261028
Compared against integration/phase2-phase3-20261027 at 2ca95fa1aa8206ec8763443d8256ab54ac789017.
Comparison: ahead 4 commits, behind 0, four changed files before this report.

## Actual attempted command and output
Command: git ls-remote https://github.com/anigio2705-dev/hangeul-swipji.git HEAD
Exit: failed
stderr:
fatal: unable to access 'https://github.com/anigio2705-dev/hangeul-swipji.git/': Could not resolve host: github.com

No repository checkout was available in the command execution environment. Therefore neither Python regression tests nor phase3/instant-browser-test.cjs was executed. There are no test PASS counts or browser logs to report.

## Evidence classification
- SOURCE REVIEW ONLY: pagehide timer=null fix; instant queue TTL=45; offer TTL=60; SQLite unique open-match indexes; approved partner/teacher eligibility; both-ready room URL release.
- NOT EXECUTED: Python HTTP regression suite; Playwright browser suite; real back/forward history; reload; network offline/reconnect; expired queue; concurrent duplicate matching; unauthorized reserved lesson room; unapproved teacher role.
- NOT VERIFIED: public deployment, actual two-device bidirectional video and audio.
- EXISTING TEST COVERAGE, NOT A PASS: phase3/test_instant_matching.py has concurrent join, stale queue, role revocation, unapproved partner; phase3/instant-browser-test.cjs has mocked Jitsi dual-context flow and reload/pagehide additions.
- SECURITY LIMIT: Jitsi room URL access is external to the application API; no provider-level identity gate has been demonstrated.

## Team11 contract dependencies
Current code assumes users.id, users.role in learner/partner/teacher and global users.approved. Team11 multi-role model and scoped approval may differ. Instant state idle/waiting/offered/active and match table state offered/active/ended are separate from booking states. Confirm shared IDs, role-scoped approvals, room-access contract and transitions with Team11 before altering common schema.

## Required next commands (on a machine with checkout and dependencies)
git checkout team13/platform-bfcache-reconnect-20261028
python3 -m unittest discover -s phase3 -p 'test_*.py' -q
node phase3/instant-browser-test.cjs
Capture exit codes, stderr/stdout, browser errors and actual test counts. Use isolated DB and intercepted Jitsi media. For real browser back/forward, offline/online and booking authorization, add/run dedicated tests only after a reproducible baseline.
No implementation changes made in third pass; no integration or deployment.
