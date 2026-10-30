# AI Team Knowledge — shared evidence index

This is an evidence-first, cross-team knowledge base. A case is **not** a deployment success merely because a CI check passes.

## Directories
- `SUCCESS/`: proven successes with exact verification scope
- `FAILURE/`: reproduced failures and rejected hypotheses
- `LESSONS/`: reusable engineering rules and limitations
- `CROSS_TEAM/`: cross-team adoption attempts and independent outcomes

## Case workflow
1. Before work, search this index and linked cases for similar symptoms.
2. Record case ID, team, backlog task, reproduction, hypothesis, attempted fix, changed paths, commit SHA, CI URL, independent check, caveats, cross-team targets, next task.
3. Record distinct gates: code changed / focused test / independent test / integration / staging99 deployment / browser verification.
4. Link a reuse attempt from `CROSS_TEAM/` and classify as unchanged success, adapted success, failed, or not applicable.
5. Promote a lesson only after independent reproduction and multiple validated applications.
6. Never claim an AI-agent call or an automatic handoff without API logs and next-task evidence.

## Initial cases
- [Professional education baseline mismatch](FAILURE/20261030-team15-professional-baseline.md)
- [CI runtime environment portability](SUCCESS/20261030-team12-ci-environment.md)
- [Preservation and fail-closed principles](LESSONS/preservation-and-fail-closed.md)
- [Cross-team adoption template](CROSS_TEAM/TEMPLATE.md)

## Case template
`ID | Team | 160 task # | Symptom | Reproduction | Initial hypothesis | Attempt/results | Root cause | Actual change/SHA | CI | Independent audit | Integration | Staging SHA/browser | Reusable lesson | Invalid conditions | Related teams | Next task`
