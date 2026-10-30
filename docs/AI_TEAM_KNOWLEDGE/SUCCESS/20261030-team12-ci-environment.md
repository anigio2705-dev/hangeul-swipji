# Scoped success: phase3 CI environment repair

- Case: KB-S-20261030-12-001
- Team: 12; shared with 11, 13, 15, 16; backlog item: to be linked by HQ
- Symptom: Phase3 isolated CI could not read historical commit via `git show` with shallow checkout, then Playwright browser dependencies failed on unsupported Ubuntu image.
- Changes: `.github/workflows/phase3-isolated-tests.yml` set checkout `fetch-depth: 0` and pinned runner `ubuntu-24.04`.
- Commits: `0a5ab4b97310a6f4d512de101dc279ab29eaa49f` and `a7bd7b51a85027eb8db35b6d3f2a068149c3842d`.
- Focused CI: https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40975208410 — SUCCESS.
- Full integration on same team12 head: https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40975208414 — SUCCESS.
- Scope: success for this branch and CI environment only. No claim of Render staging99 deployment or human audio listening approval.
- Reusable lesson: check checkout depth and runner compatibility before changing application code in response to CI setup errors.
- Invalid conditions: cannot blindly pin obsolete OS versions or fetch full history without evaluating resource and security constraints.
- Cross-team action: 15 team independently compare equivalent CI failures before adoption.
