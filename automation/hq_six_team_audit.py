"""Read-only HQ six-team evidence audit. Never treats commits as backlog completion."""
import json
import os
from urllib.request import Request, urlopen
from urllib.error import HTTPError

REPO = "anigio2705-dev/hangeul-swipji"
TEAMS = ("11", "12", "13", "14", "15", "16")
BRANCH_PREFIX = "automation/hq-team-"
BRANCH_SUFFIX = "-autodev-20261029"

def api(path, token):
    request = Request("https://api.github.com/repos/" + REPO + path,
                      headers={"Accept": "application/vnd.github+json",
                               "Authorization": "Bearer " + token,
                               "User-Agent": "hq-six-team-audit"})
    with urlopen(request, timeout=25) as response:
        return json.load(response)

def evaluate(team, branch, head, runs):
    relevant = [r for r in runs if r.get("head_sha") == head]
    passing = [r for r in relevant if r.get("conclusion") == "success"]
    failing = [r for r in relevant if r.get("conclusion") in ("failure", "timed_out", "cancelled")]
    if failing and not passing:
        verdict = "REWORK"
        instruction = "Investigate failed CI; repair and rerun tests on isolated branch"
    elif passing:
        verdict = "REVIEW"
        instruction = "Independently inspect changed functionality, cross-team integration and backlog evidence"
    else:
        verdict = "UNVERIFIED"
        instruction = "Run meaningful tests and attach CI evidence; no completion credit"
    return {"team": team, "branch": branch, "head": head,
            "verdict": verdict, "instruction": instruction,
            "passing_runs": [r["html_url"] for r in passing[:3]],
            "failing_runs": [r["html_url"] for r in failing[:3]]}

def audit(token):
    report = []
    for team in TEAMS:
        branch = BRANCH_PREFIX + team + BRANCH_SUFFIX
        try:
            data = api("/branches/" + branch, token)
            head = data["commit"]["sha"]
            runs = api("/actions/runs?branch=" + branch + "&per_page=30", token)["workflow_runs"]
            report.append(evaluate(team, branch, head, runs))
        except (HTTPError, KeyError, ValueError) as error:
            report.append({"team": team, "branch": branch, "verdict": "BLOCKED",
                           "instruction": "Inspect branch/API access and retry",
                           "error": str(error)[:160]})
    return {"schema": 1, "scope": "read-only verification, not dispatch or deployment",
            "teams": report, "completed_backlog_items": "not established",
            "next_action": "HQ must connect decisions to real team assignments and retest"}

def main():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required")
    result = audit(token)
    with open("hq-six-team-audit.json", "w", encoding="utf-8") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
