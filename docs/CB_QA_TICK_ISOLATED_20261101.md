# C/B exact-SHA QA poll — isolated 4-minute controller template (2026-11-01)

**Status: CODE + SYNTHETIC CI ONLY. NOT INSTALLED, NOT ENABLED, NOT HOST_GO.**
This is a separate C/B autonomous-development lane. It does not alter A's 160-item
READY queue, the existing A/B/C/D Render dry-run, TEST99, production, or main.

## Existing components reused

- PR #162: durable work queue, lease/fencing, future isolated AI executor.
- PR #168: CI polling, durable QA outbox and host service templates.
- PR #248: read-only authenticated GitHub B evidence verifier, immutable
  exact-SHA receipt store, and new `cb_qa_tick.py` bridge.
- PR #253: separate Render rotation planning experiment; no dependency on it.

## What the new tick actually does

1. A protected controller pins source PR + product SHA and B QA PR + QA SHA
   + Actions run ID + distinct allowlisted B reviewer.
2. The tick claims a short SQLite lease on a persistent volume. Active leases
   suppress overlapping polls; expired read-only leases may be recovered.
3. It fetches GitHub evidence via GET, verifies the B-only PR's exact base,
   exact QA SHA, independent reviewer, Actions run, and QA-only file list.
4. Unverified or absent B evidence is **WAITING**, not a fabricated QA_FAIL.
5. A verified result becomes an immutable receipt:
   - QA_PASS -> `QA_PASS_VERIFIED` / **await A's separate decision**.
   - QA_FAIL -> `C_REWORK_REQUIRED` / **no Codex execution or push**.
   - Retry limit -> `BLOCKED_245` / manual review.
6. The next tick is due 240 seconds later if evidence is still missing.
   Exceptions are redacted before durable logging.

The new `hangeul-cb-qa-tick.service/.timer` are **disabled templates**. The
timer declares a four-minute calendar interval; no real service was started.
It requires a root-owned controller, dedicated least-privilege user, protected
environment, credential file, and `/var/lib/hangeul-swipji` mount point.

## Protected environment contract (not a deployment instruction)

```text
CB_DB_PATH=/var/lib/hangeul-swipji/cb-qa.sqlite3
CB_REQUEST_ID=HUB-20261101-C-002
CB_SOURCE_PR=<source PR number>
CB_PRODUCT_SHA=<exact 40-character product SHA>
CB_QA_PR=<independent B-only PR number>
CB_QA_SHA=<exact 40-character QA SHA>
CB_QA_RUN_ID=<exact Actions run ID>
CB_TRUSTED_B_LOGIN=<distinct independently controlled B account>
```

The token must be loaded through systemd credentials, never stored in GitHub,
comments, or the environment file. A C-controlled account or C-authored
review cannot be treated as independent B approval. GitHub PR/Actions
provenance alone is not proof of host process isolation.

## Explicitly NOT implemented or proven

- B QA PR/run discovery from #245 without protected configuration.
- Distinct independently controlled B reviewer/credential in the real repo.
- Automatic enqueue of Codex rework after a verified QA_FAIL.
- Authenticated Codex calls, two consecutive tasks, remote push broker.
- Actual host installation, restart across host reboot, or 24-hour uptime.
- B QA PASS for the current PR #248 head.
- A READY promotion, product deployment, or any new Render service.

Do not enable the timer until B independently validates the current exact SHA,
OS process isolation, persistent volume, token scope, cost limits and fencing.
Never infer a real 4-minute autonomous AI cycle from synthetic CI success.

## Regression suite

`test_cb_qa_tick.py` exercises valid PASS/FAIL receipts, same-account
rejection, stale Actions, missing review, no secret leakage on GET failure,
active lease/expiry recovery, pinned SHA immutability, retry-limit escalation
and separation from A READY. These are synthetic fixtures, not real B QA.

The host workflow now runs any future B QA-only `test_bqa_*.py` automatically
so a B-only PR need not modify the CI workflow. A separate B reviewer identity
and raw Actions evidence are still required for an independent verdict.
