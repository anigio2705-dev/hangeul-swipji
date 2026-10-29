# HQ2 holdout eval — #22 reservation read-only side effects (2026-10-29 17:08 KST)

## Hypothesis and unseen failure
An HTTP endpoint documented as a read-only reservation bridge should not expire an unrelated instant-match offer or delete queue rows. Prior tests covered booking ownership and 403/409 authorization but not a stale queue encountered while browsing reservations.

## Reproduction (actual isolated CI)
- New real HTTP + disposable SQLite regression: `phase3/test_instant_matching.py::InstantMatchingTests.test_reservation_list_does_not_mutate_stale_instant_match`.
- Original implementation failed: expected `instant_matches.state='offered'`, observed `'ended'`; exact pre-fix CI [40839827941](https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40839827941), head `c5bf20d2c91c97aa9a7bf0e3c2fb3a2cd18078d2`.
- Root cause: `instant_matching.route()` called `cleanup(db, now)` before handling **all** actions, including read-only `reservations`. TTL expiry was a hidden write on an unrelated GET.

## Minimal repair and same-test replay
- Repair `phase3/instant_matching.py` at `b68e71dc9a1d0cc9c55f6ff8a4b26540b2ceed2b`: exclude **only** read-only `reservations` from cleanup; all other endpoint cleanup semantics remain unchanged. An earlier broader patch `51d85101` passed CI but was narrowed to the directly tested action.
- Earlier broader patch CI [40839882956](https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40839882956) **SUCCESS**: 21 actual HTTP/SQLite instant-matching tests and 5 independent pure contract tests, including the preexisting booked-session 403 case. **The narrowed patch requires its own exact-SHA CI before acceptance.**
- Draft review [PR #29](https://github.com/anigio2705-dev/hangeul-swipji/pull/29) targets only the approved HQ isolated branch; **not merged**, not deployed to test99, no production or real payments.

## AGI ability rubric, separate from 160 acceptance
- **A / deterministic CI:** PASS (failure captured then repaired in independent GitHub runner).
- **B / autonomous team AI developer:** NOT PROVEN. This was HQ2 direct code work; no new 11–16 team model invocation or bot commit.
- **C / continuous multi-team self-development:** NOT PROVEN. No three successive independent developer→QA→handoff cycles.
- **D / holdout transfer:** One newly identified side-effect class reproduced and repaired in a new test; **not** evidence of general-purpose transfer or AGI.
- **Memory / reusable failure pattern:** Any read-only bridge must be checked for hidden lifecycle writes before returning; add an isolated HTTP+SQLite counterexample for a stale record, then confirm that the proper lifecycle endpoint still expires it.
- **Next independent 15-team review:** assess read-only reservation semantics and whether other actions have separate hidden side effects; verify #22 existing 403/200 reservation collision, same-room participant/outsider checks, and test99 hosted browser acceptance. #22 remains BLOCKED and owner approval 0.

## Official method references
- OpenAI, [Build an Agent Improvement Loop with Traces, Evals, and Codex](https://developers.openai.com/cookbook/examples/agents_sdk/agent_improvement_loop): turn observed failure into repeatable eval before accepting repair.
- OpenAI Agents SDK, [Guardrails](https://openai.github.io/openai-agents-python/guardrails/): fail-closed boundaries before tool actions; an analogy for safety gates, not proof this repository uses the SDK.

This is a bounded regression experiment, not a claim of autonomous AGI, real user E2E, or final contract completion.
