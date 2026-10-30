# TEAM16-STAGING-FAILURES-20261030

**Owner:** Team 16; integration issues shared with Teams 11, 12, 15 and HQ. **Backlog number:** not verified.

## Failure A: Playwright Chromium install
- **Observed:** integration CI failed during browser dependency installation.
- **Hypothesis:** unsupported/default runner and transient dependency installation problems.
- **Correction:** pin `ubuntu-24.04` and add up to three installation retries plus disk diagnostics in `.github/workflows/integration-validation.yml`.
- **Evidence:** staging integration commit `5fefd181071ab819b272c979742db1b58ad9103a`; browser install subsequently advanced to Python tests.
- **Lesson:** distinguish infrastructure failures from product failures; retries are bounded and do not replace root cause analysis.

## Failure B: immutable education homepage source
- **Observed:** Python original-material preservation check failed after preview-only markup modified `index.html`.
- **Correction:** remove preview banner from immutable source and separate team-specific handoff from original pages.
- **Evidence:** Team16 staging commit `2bc64bcdb8dbd6f49722be83d1d8450d61848d03`; later HQ integration adjustments restored additional immutable learning pages.
- **Lesson:** stage optional previews outside source-protected education files; check byte-level preservation before integration.

## Failure C: audio runtime regression on integration branch
- **Observed:** `scripts/check-audio-runtime.cjs:14`, expected `played` but received `error` in https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40975081079.
- **Status:** observed failure, not claimed solved here.
- **Ownership:** Team 11 audio runtime, Team 12 education/audio, Team 15 independent QA.
- **Next:** reproduce with exact source SHA, inspect manifest/audio loading and event contracts, fix product or faithful test fixture, rerun integration.

**Caution:** Each case is scoped to its cited branch and SHA. A later CI pass on a different branch is not proof that these cases are integrated or deployed to test99.
