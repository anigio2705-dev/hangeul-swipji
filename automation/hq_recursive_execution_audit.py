"""Read-only evidence gate for six recursive team HQs.

A defined role is not an executed agent. The gate never independently verifies
GitHub links: only call IDs supplied by an independent verifier can count.
Even a complete manifest is REVIEW_REQUIRED, never OWNER_APPROVED.
"""
import argparse
import json
import re
from pathlib import Path

OWNERS = {
    "11": ((11, 20), (31, 40), (131, 140)),
    "12": ((41, 70),),
    "13": ((21, 30), (81, 100)),
    "14": ((71, 80), (101, 130)),
    "15": ((1, 10), (151, 160)),
    "16": ((141, 150),),
}
ROLES = {"discovery", "implementation", "qa", "repair", "queue"}
SHA = re.compile(r"^[0-9a-f]{40}$")
RUN = re.compile(r"^https://github\.com/[^/]+/[^/]+/actions/runs/[0-9]+$")


def owned(team, task):
    return type(task) is int and any(lo <= task <= hi for lo, hi in OWNERS[team])


def assess(manifest, independently_verified_call_ids=()):
    """Return conservative per-team verdicts. No network or code writes."""
    if not isinstance(manifest, dict) or not isinstance(manifest.get("events", []), list):
        raise ValueError("events must be a list")
    verified = set(independently_verified_call_ids)
    events = manifest.get("events", [])
    seen = set()
    grouped = {team: [] for team in OWNERS}
    errors = []
    for idx, event in enumerate(events):
        if not isinstance(event, dict):
            errors.append(f"event {idx}: not an object")
            continue
        team, role, call = str(event.get("team", "")), event.get("role"), event.get("call_id")
        if team not in OWNERS or role not in ROLES or not isinstance(call, str) or not call.strip():
            errors.append(f"event {idx}: invalid team, role or call_id")
            continue
        if call in seen:
            errors.append(f"event {idx}: duplicated call_id {call}")
            continue
        seen.add(call)
        task = event.get("task_number")
        if not owned(team, task):
            errors.append(f"event {idx}: team {team} does not own task {task}")
            continue
        grouped[team].append(event)
    result = {}
    for team, team_events in grouped.items():
        trusted = [e for e in team_events if e["call_id"] in verified]
        roles = {e["role"] for e in trusted}
        implementations = [e for e in trusted if e["role"] == "implementation"
                           and isinstance(e.get("commit_sha"), str)
                           and SHA.fullmatch(e["commit_sha"])
                           and isinstance(e.get("changed_files"), list)
                           and bool(e["changed_files"])]
        qa = [e for e in trusted if e["role"] == "qa"
              and e.get("ci_result") == "success"
              and isinstance(e.get("ci_url"), str)
              and RUN.fullmatch(e["ci_url"])]
        queue = [e for e in trusted if e["role"] == "queue"
                 and owned(team, e.get("next_task_number"))
                 and e["next_task_number"] != e["task_number"]]
        independent_pair = any(
            i["task_number"] == q["task_number"] and i["call_id"] != q["call_id"]
            for i in implementations for q in qa
        )
        has_failure = any(e.get("outcome") == "failed" for e in trusted)
        repair_ok = not has_failure or "repair" in roles
        if not team_events:
            status = "NOT_PROVEN"
        elif not trusted:
            status = "UNVERIFIED"
        elif {"discovery", "implementation", "qa", "queue"} <= roles and implementations and independent_pair and queue and repair_ok:
            status = "REVIEW_REQUIRED"
        else:
            status = "INCOMPLETE"
        result[team] = {
            "status": status,
            "claimed_calls": len(team_events),
            "independently_verified_calls": len(trusted),
            "roles_with_verified_calls": sorted(roles),
            "new_code_commits_with_diff": len(implementations),
            "independent_qa_pair": bool(independent_pair),
            "next_queue_evidence": bool(queue),
            "repair_evidence_if_failed": bool(repair_ok),
        }
    return {"teams": result, "invalid_events": errors, "owner_approved": False,
            "note": "REVIEW_REQUIRED is not CI verified, deployed, or owner approved."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--verified-calls", type=Path, help="Independent verifier output: JSON list of call IDs")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    verified = json.loads(args.verified_calls.read_text(encoding="utf-8")) if args.verified_calls else []
    print(json.dumps(assess(manifest, verified), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
