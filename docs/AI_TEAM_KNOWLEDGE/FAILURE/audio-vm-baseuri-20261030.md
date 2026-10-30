# CASE-20261030-AUDIO-VM-BASEURI — Node VM audio fixture failure

Team: 11 / 15 / 16 cross-team integration. Backlog task ID: not independently established.

## Reproduction and cause
Integration CI [40975086744](https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40975086744) failed in `node scripts/check-audio-runtime.cjs`: `'error' !== 'played'`. Production `hangul-core.js` resolves an audio file via `new URL(records[word].src, document.baseURI)`, while the Node VM mock document lacked `baseURI`. The browser emulation, not necessarily the real recording, was defective.

## Fix and evidence
Added `baseURI:'https://hangeul-swipji.test/'` to the mocked document in `scripts/check-audio-runtime.cjs`. Fix commit [a1d86123885fc6449133be9e66691cb1b23ce71a](https://github.com/anigio2705-dev/hangeul-swipji/commit/a1d86123885fc6449133be9e66691cb1b23ce71a). [CI rerun 40975415841](https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40975415841): check outcome separately; no claim of independent PASS or staging99 deployment here.

## Cross-team reuse
11: keep production audio unchanged when fixture is wrong. 12: independently validate actual learning-screen playback. 15: preserve strict playback assertions and run browser/mobile regression. 16: ensure integration checks exercise correct browser APIs.

Do not apply this fixture URL to production, bypass human-recording approval, or treat CI as proof of deployed audio. Record future adoption and independent results in `CROSS_TEAM/`.
