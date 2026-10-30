# Failure: professional-96 original preservation comparison

- Case: KB-F-20261030-15-001
- Team: 15; relevant team: 12; backlog item: to be confirmed by HQ
- Symptom: Full integration workflow failed although independent held-audio smoke passed.
- Reproduction: GitHub Actions run https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40989371371 ; job 123847797397; step `python scripts/audit-professional-96.py`.
- Observed: 96 units, 72 new units, 288 assessments, zero exact passage duplicates; nine `original modified` errors: intro.html, beginner1.html, beginner2.html, intermediate1.html, intermediate2.html, advanced1.html, advanced2.html, reading.html, index.html.
- Hypothesis A: staging-approved changes compared against an obsolete baseline. **Not yet established for this specific branch**; inspect nine diffs and compare to approved baseline.
- Alternative B: unintended original content modifications. Restore only those changes confirmed unauthorized.
- Related prior evidence: team12 PR #87 full integration run https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40975208414 succeeded on a different branch; this does not prove team15 branch safe.
- Current result: integration FAIL; no staging99 deployment evidence.
- Next: team12 + team15 compare original vs approved staging blobs, retain strict preservation audit, modify code or restore unauthorized changes, rerun focused and full CI.
- Lesson: preserve original content; never weaken tests just to obtain green.
