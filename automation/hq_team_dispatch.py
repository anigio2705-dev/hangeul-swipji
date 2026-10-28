"""Six-team isolated HQ dispatcher: validate branch ownership and publish team work queues."""
import json
import os
from pathlib import Path
import subprocess
import sys

TEAMS = {
 "11": {"branch": "team11/common-foundation-20261028", "scope": "shared foundation, authentication, localization"},
 "12": {"branch": "team12/education-audit-20261028", "scope": "350 lessons, reading, audio and education"},
 "13": {"branch": "team13/platform-bfcache-reconnect-20261028", "scope": "matching, browser and video platform"},
 "14": {"branch": "team14/business-systems-audit-20261028", "scope": "booking, settlement, refund and referral"},
 "15": {"branch": "team15/quality-operations-20261028", "scope": "independent regression and evidence gates"},
 "16": {"branch": "team16/global-growth-marketing-20261028", "scope": "internationalization, growth and marketing"},
}
def main():
    team = os.environ.get("HQ_TEAM", "")
    if team not in TEAMS:
        raise SystemExit("Invalid team")
    if os.environ.get("GITHUB_REF_NAME") != "automation/hq-pilot-13-14-15-20261029":
        raise SystemExit("Isolated HQ ref required")
    entry = TEAMS[team]
    result = subprocess.run(["git", "ls-remote", "--exit-code", "origin", "refs/heads/" + entry["branch"]],
                            capture_output=True, text=True, timeout=45)
    if result.returncode:
        raise SystemExit("Team branch unavailable")
    evidence = {"team": team, "branch": entry["branch"], "head": result.stdout.split()[0],
                "scope": entry["scope"], "status": "branch_verified",
                "development_status": "not_started",
                "note": "Parallel ownership audit only; no six autonomous AI developers yet."}
    Path("team-dispatch-result.json").write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence))

if __name__ == "__main__":
    main()
