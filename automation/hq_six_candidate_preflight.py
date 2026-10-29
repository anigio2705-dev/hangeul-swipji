"""Read-only six-team READY intake: actionable evidence, never self-approval."""
import argparse
import json
from pathlib import Path
from hq_160_task_cycle import load_catalog
from hq_traffic_lights import TEAMS, readiness


def summarize(catalog, ledger, registry, root):
    queue = readiness(catalog, ledger, registry, root=root)
    teams = {}
    for team in TEAMS:
        candidates = []
        for candidate in queue["candidate_supply"].get(team, []):
            number = candidate["task"]
            entry = registry["items"][str(number)]
            source = entry.get("source_paths", [])
            tests = entry.get("test_paths", [])
            editable = entry.get("editable_path")
            if editable is None and len(source) == 1:
                editable = source[0]
            blockers = list(candidate["blockers"])
            if not entry.get("independent_ci_url"):
                blockers.append("exact_sha_independent_ci_missing")
            if not editable or editable not in source:
                blockers.append("single_editable_path_missing")
            elif not editable.endswith(".py") or editable.startswith(("automation/", ".github/")):
                blockers.append("current_python_runner_cannot_edit_target")
            if not tests or not all(
                p.endswith(".py") and Path(p).name.startswith("test_") for p in tests
            ):
                blockers.append("independent_python_unittest_missing")
            if team == "15":
                blockers.append("team15_own_task_requires_external_independent_qa")
            candidates.append({
                "task": number, "editable_path": editable,
                "test_paths": tests, "blockers": sorted(set(blockers)),
                "unmet_acceptance": candidate.get("unmet_acceptance", []),
                "ready": False,
            })
        candidates.sort(key=lambda x: (len(x["blockers"]), x["task"]))
        teams[team] = {
            "candidate_count": len(candidates),
            "next_candidate": candidates[0]["task"] if candidates else None,
            "next_blockers": candidates[0]["blockers"] if candidates else ["no_mapped_candidate"],
            "candidates": candidates,
        }
    return {
        "schema": 1, "policy": "READ_ONLY; candidate intake is not READY or AI execution",
        "mapped_total": queue["mapped_total"],
        "dispatchable_total": queue["dispatchable_total"],
        "teams": teams,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="/tmp/hq-six-ready-intake.json")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    catalog = load_catalog(str(root / "automation/hq_backlog_160.md"))
    ledger = json.loads((root / "automation/task-evidence.json").read_text())
    registry = json.loads((root / "automation/hq_semantic_contract_paths.json").read_text())
    report = summarize(catalog, ledger, registry, root)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "mapped": report["mapped_total"],
        "READY": report["dispatchable_total"],
        "next": {team: data["next_candidate"] for team, data in report["teams"].items()},
        "blockers": {team: data["next_blockers"] for team, data in report["teams"].items()},
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
