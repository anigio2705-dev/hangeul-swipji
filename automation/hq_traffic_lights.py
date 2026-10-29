"""HQ traffic-light decision engine. Read-only; never equate green CI with finished product."""
import json
from pathlib import Path

TEAMS = ("11", "12", "13", "14", "15", "16")
FINAL = {"complete"}
VERIFIED = {"code_verified", "complete"}
ACTIVE = {"in_progress", "retry"}
RED = {"blocked", "retry"}

def evaluate(catalog, ledger, active_runs=0, failure_runs=0):
    if set(TEAMS) - {str(t["owner"]) for t in catalog.values()}:
        raise ValueError("Six-team ownership is incomplete")
    result = {}
    for team in TEAMS:
        owned = [t for t in catalog.values() if t["owner"] == team]
        verified = [t["number"] for t in owned if ledger.get(str(t["number"]), {}).get("status") in VERIFIED]
        completed = [t["number"] for t in owned if ledger.get(str(t["number"]), {}).get("status") in FINAL]
        blocked = [t["number"] for t in owned if ledger.get(str(t["number"]), {}).get("status") in RED]
        pending = [t["number"] for t in owned if ledger.get(str(t["number"]), {}).get("status") not in VERIFIED | RED]
        if blocked:
            light, action = "RED", "ISSUE_TARGETED_REPAIR"
        elif pending:
            light, action = "YELLOW", "VERIFY_OR_ASSIGN"
        else:
            light, action = "GREEN", "REVIEW_INTEGRATION"
        result[team] = {"light": light, "action": action, "owned": len(owned),
                        "code_verified": len(verified), "final_complete": len(completed),
                        "blocked_tasks": blocked, "pending_tasks": pending[:12]}
    return {"schema": 1, "total": len(catalog), "final_complete": sum(
        ledger.get(str(n), {}).get("status") == "complete" for n in catalog),
        "code_verified": sum(ledger.get(str(n), {}).get("status") in VERIFIED for n in catalog),
        "active_runs": active_runs, "recent_failed_runs": failure_runs,
        "teams": result, "rule": "Green team status is not final backlog completion."}


def readiness(catalog, ledger, registry, root=Path(".")):
    """Conservative contract queue: no guessed paths or self-approved READY.

    This checks local source/test paths and recorded independent review. A CI
    URL alone is NOT a live CI verification; the dispatch supervisor must
    recheck its conclusion and the exact commit before accepting any patch.
    """
    import re
    if registry.get("schema") != 1 or not isinstance(registry.get("items"), dict):
        raise ValueError("Invalid HQ semantic registry")
    entries = registry["items"]
    unknown = set(entries) - {str(n) for n in catalog}
    if unknown:
        raise ValueError("Unknown semantic contract IDs: " + ", ".join(sorted(unknown)))
    result = {"mapped_total": len(entries), "unmapped_total": len(catalog) - len(entries),
              "dispatchable_total": 0, "dispatchable": [], "candidates": [],
              "blocked": [], "invalid_ready": [], "already_verified": [],
              "unmapped_unverified": []}
    base = Path(root).resolve()
    def valid_path(raw):
        if not isinstance(raw, str) or not raw or raw.startswith("/"):
            return False
        p = (base / raw).resolve()
        return p.is_relative_to(base) and p.is_file()
    for number, task in catalog.items():
        key = str(number)
        state = ledger.get(key, {}).get("status", "unverified")
        entry = entries.get(key)
        if state in VERIFIED:
            result["already_verified"].append(number)
            continue
        if not entry:
            result["unmapped_unverified"].append(number)
            continue
        if state == "blocked" or entry.get("state") == "BLOCKED":
            result["blocked"].append(number)
            continue
        if entry.get("state") == "CANDIDATE":
            result["candidates"].append(number)
            continue
        if entry.get("state") != "READY":
            result["invalid_ready"].append({"task": number, "reason": "No approved READY state"})
            continue
        source = entry.get("source_paths")
        tests = entry.get("test_paths")
        ci = entry.get("independent_ci_url", "")
        # Multiple observed files are allowed as read-only context only when
        # a single, explicit editable file is independently authorized.
        editable = entry.get("editable_path")
        source_list = isinstance(source, list) and bool(source)
        editable_ok = source_list and (
            (len(source) == 1 and (editable is None or editable == source[0]))
            or (len(source) > 1 and isinstance(editable, str) and editable in source)
        )
        authorized = entry.get("owner") == task["owner"] and set(entry.get("support", [])) <= set(task["support"])
        reviewed = entry.get("independent_team15") == "PASS"
        ci_ref = isinstance(ci, str) and bool(re.fullmatch(
            r"https://github\.com/anigio2705-dev/hangeul-swipji/actions/runs/[0-9]+", ci))
        paths = (isinstance(source, list) and bool(source)
                 and isinstance(tests, list) and bool(tests)
                 and len(source) == len(set(source))
                 and len(tests) == len(set(tests))
                 and not set(source).intersection(tests)
                 and all(valid_path(p) for p in source + tests))
        deps = all(ledger.get(str(d), {}).get("status") == "complete"
                   for d in task["dependencies"])
        if not (authorized and reviewed and ci_ref and paths and deps and editable_ok):
            missing = [name for name, ok in (("owner", authorized), ("independent_review", reviewed),
                ("ci_reference", ci_ref), ("real_paths", paths),
                ("single_editable_path", editable_ok), ("dependencies", deps)) if not ok]
            result["invalid_ready"].append({"task": number, "reason": ", ".join(missing)})
            continue
        assignment = {"task": number, "owner": task["owner"],
                      "source_paths": source}
        if editable is not None:
            assignment["editable_path"] = editable
        result["dispatchable"].append(assignment)
    # A file cannot be owned by two parallel READY assignments. Reject both
    # rather than silently letting iteration order choose an unsafe winner.
    owners_by_path = {}
    for assignment in result["dispatchable"]:
        for path in assignment["source_paths"]:
            owners_by_path.setdefault(path, set()).add(assignment["task"])
    conflicts = {}
    for path, tasks in owners_by_path.items():
        if len(tasks) > 1:
            for number in tasks:
                conflicts.setdefault(number, set()).add(path)
    if conflicts:
        result["dispatchable"] = [assignment for assignment in result["dispatchable"]
                                  if assignment["task"] not in conflicts]
        for number in sorted(conflicts):
            result["invalid_ready"].append({
                "task": number,
                "reason": "exclusive_file_collision: " + ", ".join(sorted(conflicts[number])),
            })
    # READY=0 must produce an actionable six-team intake report rather than
    # an empty WAIT. This is diagnostic only: no CANDIDATE is promoted here.
    # In particular, the current AI patch verifier accepts exactly one source
    # file; multi-file candidates need a separate reviewed execution path.
    supply = {team: [] for team in TEAMS}
    for number in result["candidates"]:
        entry = entries[str(number)]
        task = catalog[number]
        source = entry.get("source_paths", [])
        tests = entry.get("test_paths", [])
        blockers = []
        if entry.get("owner") != task["owner"]:
            blockers.append("owner_mismatch")
        if not isinstance(source, list) or not source or not all(valid_path(p) for p in source):
            blockers.append("missing_or_invalid_source_path")
        elif len(source) != 1 and entry.get("editable_path") not in source:
            blockers.append("explicit_single_editable_path_required")
        if not isinstance(tests, list) or not tests or not all(valid_path(p) for p in tests):
            blockers.append("missing_or_invalid_test_path")
        if entry.get("independent_team15") != "PASS":
            blockers.append("team15_independent_review_pending")
        if any(ledger.get(str(dep), {}).get("status") != "complete"
               for dep in task["dependencies"]):
            blockers.append("dependencies_not_complete")
        supply[task["owner"]].append({
            "task": number,
            "source_paths": source if isinstance(source, list) else [],
            "test_paths": tests if isinstance(tests, list) else [],
            "blockers": blockers,
            "unmet_acceptance": entry.get("unmet", []),
            "state": "CANDIDATE",
        })
    for team in TEAMS:
        supply[team].sort(key=lambda item: (len(item["blockers"]), item["task"]))
    result["candidate_supply"] = supply
    result["candidate_supply_next"] = {
        team: (items[0]["task"] if items else None) for team, items in supply.items()
    }
    result["dispatchable_total"] = len(result["dispatchable"])
    result["rule"] = ("READY is a static queue candidate only; exact SHA, live CI and "
                      "independent task regression must be revalidated before promotion.")
    return result

def main():
    from hq_160_task_cycle import load_catalog
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", default="automation/hq_backlog_160.md")
    parser.add_argument("--ledger", default="automation/task-evidence.json")
    parser.add_argument("--output", default="automation/hq-traffic-lights.json")
    args = parser.parse_args()
    ledger = json.loads(Path(args.ledger).read_text())
    catalog = load_catalog(args.catalog)
    report = evaluate(catalog, ledger)
    registry = json.loads(Path("automation/hq_semantic_contract_paths.json").read_text(encoding="utf-8"))
    report["dispatch_readiness"] = readiness(catalog, ledger, registry)
    assert report["final_complete"] <= report["code_verified"] <= 160
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"final_complete": report["final_complete"],
                      "code_verified": report["code_verified"],
                      "team_lights": {t: x["light"] for t, x in report["teams"].items()}}, ensure_ascii=False))
if __name__ == "__main__":
    main()
