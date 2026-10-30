# 15팀 독립 P0 음성 보류 우회 검증 — 2026-10-30

Source PR: #127, source product SHA `eb8a144a0bb88ca41fa30811c62467fa8d96971a`.
Base integration SHA `a5ac3c5019a3fe70ee9525bc298887e202c37667`.

Reproduction: a human recording explicitly marked `disabled:true` may have its
file URL or digest removed during quarantine, or share a duplicate source. Old
`hangul-core.js` filtered it out as missing and let opt-in TTS speak a
review-held sound. No human audio can be claimed as approved without listening.

RED: https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/41009220434
(2 independent negative tests failed).
GREEN: https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/41009293943
(28/28 Node tests + runtime check passed).

Change: preserve disabled entries as `held` before validating playable
MP3 metadata, retain hard hold for direct and sequence TTS; cache-bust both
learner surfaces. This document is an isolated integration-test trigger,
not deployment approval.

No main/production data/payment changes. Render test99 redeploy prohibited
until current SHA, SQLite persistence, backup, restore and rollback are proven.
PC/mobile human listening and two-device Jitsi remain separate acceptance gates.
