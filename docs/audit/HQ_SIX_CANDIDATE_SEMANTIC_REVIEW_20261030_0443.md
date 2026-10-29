# Six-team candidate artifact independent semantic audit — 2026-10-30 04:43 KST

## Scope and evidence
Latest six-team Actions run: https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40942363041 (6 develop jobs + supervisor completed SUCCESS). Previous run: https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40942082940. The source registry `automation/hq_semantic_contract_paths.json` has 24 mapped tasks, 0 READY. Bot-authored exploratory candidate JSON files **are not product source changes**, not 15-team semantic approval, and not 160-task completion.

| Team | Task | Bot commit (isolated team branch) | Independent content review |
|---|---:|---|---|
| 11 | #11 | a680a12fe21f97ea669bbd62b667c8bb82a2989d | FAIL: stale checkout case allows warning/override, contradicting fail-closed HEAD preflight contract. |
| 12 | #45 | 089f056434ae9be14e882ff775368f9c9fb130ed | RETRY: `는` in `저는` is topic marker, not a subject marker; 'one' must specify native vs Sino-Korean counting. |
| 13 | #22 | f01715f4f7cd20e51efef53dd1be306a5ec40ce6 | RETRY: no explicit HTTP 403 assertion for existing-booking instant join, no executable source/test binding. |
| 14 | #101 | 3f1957dd9de07cda874fcb89bd9eb66db4b17d99 | FAIL: 'same teacher role' wrongly conflated with same user identity; all cases reject, no valid non-self introduction acceptance. Initial team14 output rejected, later bot retry created this artifact. |
| 15 | #151 | 4843c18f6a3fdcc60aa4ae0c5eb82a4b4cedb2b6 | RETRY: session recording expected without explicit consent; anonymous visitor wrongly denied *free lesson content* rather than private learner progress/dashboard. |
| 16 | #143 | f3d768ed626de890ff3385bb3735c35ab815d957 | RETRY: eight locale labels are proposed, not matched to existing UI keys/source text, no actual browser language-switch proof. |

Each bot SHA above changes only `experiments/hq-six-candidate-artifacts/teamXX/taskNN.json`. No new product code or deployed UI change was found in these commits. Six bot artifact commits are verified by GitHub commit/file metadata. The registry reports an earlier six-call attempt (five accepted) and a separate team14 retry; precise API usage/billing requires workflow result/log confirmation.

## Reproducible audit improvement
- Official method: https://developers.openai.com/cookbook/examples/agents_sdk/agent_improvement_loop — transform trace/output failures into repeatable eval cases; use independent grading, not the generator's schema success, for acceptance.
- Hypothesis: a schema-only PASS can hide contradictions in candidate semantics; deterministic red-flag checks will surface recurring concrete errors before team15 review, with zero additional model API calls.
- Isolated code: `automation/hq_six_candidate_semantic_review.py` and six new tests in `automation/test_hq_six_candidate_artifacts.py`. The tool is **diagnostic only**; does not modify the READY registry or auto-approve/reject content.
- Local offline regression: 6/6 new tests PASS. GitHub independent PR CI must be checked before adoption.
- Security: no network, credentials, production deployment, or runtime mutation. Cost: only existing Actions unittest seconds; no model spend.
- Limits: string-pattern flags are not a semantic oracle and can miss paraphrases or create false positives. Team15 must inspect the exact artifacts and source tests.

## Required next actions
1. Team11: replace stale-warning case with strict stale/dirty HEAD blocking and a reproducible source-level regression.
2. Team12: correct topic-vs-subject explanation, specify number system, verify the actual 1,758 quiz source and answer keys.
3. Team13: add explicit HTTP 403 expected result and test #22 with legitimate participant and nonparticipant.
4. Team14: distinguish same person vs same role, include at least one valid introduction, verify no real financial payout.
5. Team15: separate free lessons from private dashboards; make consent prerequisite for any recording scenario.
6. Team16: locate exact current translation keys and browser-verify all eight supported languages.
7. Independently verify all six candidate contracts and exact-SHA CI before READY; never count artifacts as six product-code commits.
8. Protect Render staging99: historical SHA 0aa0092, live SHA/DB backup not proven. No redeploy.
