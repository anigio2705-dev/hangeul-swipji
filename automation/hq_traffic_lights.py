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

def main():
    from hq_160_task_cycle import load_catalog
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", default="automation/hq_backlog_160.md")
    parser.add_argument("--ledger", default="automation/task-evidence.json")
    parser.add_argument("--output", default="automation/hq-traffic-lights.json")
    args = parser.parse_args()
    ledger = json.loads(Path(args.ledger).read_text())
    report = evaluate(load_catalog(args.catalog), ledger)
    assert report["final_complete"] <= report["code_verified"] <= 160
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"final_complete": report["final_complete"],
                      "code_verified": report["code_verified"],
                      "team_lights": {t: x["light"] for t, x in report["teams"].items()}}, ensure_ascii=False))
if __name__ == "__main__":
    main()
