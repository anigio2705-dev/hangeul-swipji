#!/usr/bin/env python3
"""Read-only evidence gate for staging99: never deploy or mutate a database.

A green CI for this module means the *blocker was detected*, not that staging99
is safe to redeploy. Historical deployment metadata cannot prove current state.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE_ID = "srv-dbg2fet9fdbs73cj08c0"


def inspect(root=ROOT):
    root = Path(root)
    blueprint = (root / "deploy/render-staging.yaml").read_text(encoding="utf-8")
    audit = json.loads((root / "audit/staging99-deployment.json").read_text(encoding="utf-8"))
    blockers = []
    if audit.get("serviceId") != SERVICE_ID:
        blockers.append("SERVICE_ID_NOT_CONFIRMED")
    if not re.search(r"(?m)^\s*autoDeployTrigger:\s*['\"]?off['\"]?\s*$", blueprint):
        blockers.append("AUTODEPLOY_NOT_DISABLED")
    if re.search(r"(?m)^\s*plan:\s*free\s*$", blueprint):
        blockers.append("FREE_PLAN_NO_PERSISTENT_DISK")
    db_path = re.search(r"(?m)^\s*value:\s*(/[^\s#]+\.sqlite3)\s*$", blueprint)
    if not db_path:
        blockers.append("SQLITE_PATH_NOT_PROVEN")
    elif db_path.group(1).startswith(("/tmp/", "/var/tmp/")):
        blockers.append("EPHEMERAL_SQLITE_DATA_LOSS")
    # The repo has no authenticated Render API snapshot, storage mount proof,
    # independently restored backup, or live deployment SHA. Never infer any of
    # these from an old deployment log, a proposed Blueprint, or a /healthz 200.
    blockers.extend((
        "CURRENT_RENDER_DEPLOY_SHA_UNVERIFIED",
        "PERSISTENT_MOUNT_UNVERIFIED",
        "BACKUP_AND_RESTORE_UNVERIFIED",
        "TEAM15_HOSTED_E2E_UNVERIFIED",
    ))
    return {
        "serviceId": SERVICE_ID,
        "historicalDeploySHA": audit.get("deployedCommit"),
        "historicalDeployIsCurrent": False,
        "safeToRedeploy": False,
        "blockers": sorted(set(blockers)),
        "nextSafeAction": "Read-only Render settings and backup/restore evidence review; no redeploy.",
    }


def main():
    report = inspect()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    # Explicit blocked exit. CI must expect code 2, not silently treat it as deploy PASS.
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
