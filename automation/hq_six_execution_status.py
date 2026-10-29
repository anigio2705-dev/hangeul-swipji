"""Report real six-team evidence without equating scheduled reports to development."""
import argparse
import json
from pathlib import Path

TEAMS = ("11", "12", "13", "14", "15", "16")

def summarize(directory):
    rows = []
    for team in TEAMS:
        path = Path(directory) / ("team-" + team + ".json")
        if not path.is_file():
            rows.append({"team": team, "status": "NOT_EXECUTED", "reason": "No team evidence file"})
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            rows.append({"team": team, "status": "BLOCKED", "reason": "Invalid evidence"})
            continue
        evidence = data.get("evidence", {})
        run_id = evidence.get("run_id") if isinstance(evidence, dict) else None
        rows.append({"team": team, "status": "UNVERIFIED" if run_id else "BLOCKED",
                     "run_id": run_id, "reason": "A self-reported run ID is not independently verified"})
    return {"overall": "UNVERIFIED", "teams": rows,
            "note": "Only GitHub Actions job logs, API invocation records and independently tested code can establish execution."}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(args.directory), ensure_ascii=False, indent=2))
