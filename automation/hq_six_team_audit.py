"""Read-only six-team evidence audit: never confuse CI or JSON with product work."""
import json
import os
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import quote

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


def changed_product_files(commit):
    """Only actual source paths count; tests, reports and candidate JSON do not."""
    if not isinstance(commit, dict):
        return []
    files = commit.get("files", [])
    if not isinstance(files, list):
        return []
    allowed_ext = (".py", ".js", ".mjs", ".cjs", ".html", ".css", ".ts", ".tsx")
    excluded_dirs = ("automation/", "docs/", ".github/", "audit/", "qa/", "tests/")
    result = []
    for item in files:
        path = item.get("filename", "") if isinstance(item, dict) else ""
        name = path.rsplit("/", 1)[-1]
        if (path and not path.startswith(excluded_dirs)
                and name.endswith(allowed_ext)
                and not name.startswith(("test_", "test-"))
                and not name.endswith((".test.js", ".test.cjs", ".spec.js", ".spec.ts"))):
            result.append(path)
    return result


def commit_time(commit):
    """Missing/unparseable timestamp means UNKNOWN, not a fabricated last-hour PASS."""
    try:
        raw = commit["commit"]["committer"]["date"]
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc)
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def evaluate(team, branch, head, runs, commit=None, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    stamp = commit_time(commit)
    changed = changed_product_files(commit)
    relevant = [r for r in runs if r.get("head_sha") == head]
    passing = [r for r in relevant if r.get("conclusion") == "success"]
    failing = [r for r in relevant if r.get("conclusion") in ("failure", "timed_out", "cancelled")]
    recent = stamp is not None and now - timedelta(hours=1) <= stamp <= now + timedelta(minutes=2)
    if stamp is None:
        verdict, instruction = "UNKNOWN", "Fetch exact commit timestamp and diff; do not infer activity"
    elif not recent:
        verdict, instruction = "STALE", "No new team HEAD commit in last hour; inspect run job logs"
    elif not changed:
        verdict, instruction = "ARTIFACT_ONLY", "JSON/report/test changes are not product code; obtain source diff"
    elif failing:
        verdict, instruction = "REWORK", "Reproduce failing CI and independently re-run on exact source SHA"
    elif passing:
        verdict, instruction = "REVIEW", "Source changed and CI passed; still verify task, AI calls, independent QA and next queue"
    else:
        verdict, instruction = "UNVERIFIED", "Run independent task-specific CI on exact source SHA"
    return {
        "team": team, "branch": branch, "head": head,
        "verdict": verdict, "instruction": instruction,
        "commit_timestamp_utc": stamp.isoformat() if stamp else None,
        "last_hour_commit": recent, "product_source_paths": changed,
        "passing_runs": [r.get("html_url") for r in passing[:3]],
        "failing_runs": [r.get("html_url") for r in failing[:3]],
        "actual_ai_calls": None, "subagent_calls": None,
        "independent_qa": "UNKNOWN", "next_task_handoff": "UNKNOWN",
        "full_autonomous_cycle": "NOT_PROVEN",
        "note": "Commit metadata/CI alone cannot establish model calls or a completed autonomous cycle"
    }


def audit(token):
    report = []
    for team in TEAMS:
        branch = BRANCH_PREFIX + team + BRANCH_SUFFIX
        try:
            data = api("/branches/" + quote(branch, safe="/"), token)
            head = data["commit"]["sha"]
            commit = api("/commits/" + head, token)
            runs = api("/actions/runs?branch=" + quote(branch, safe="") + "&per_page=30", token)["workflow_runs"]
            report.append(evaluate(team, branch, head, runs, commit))
        except (HTTPError, KeyError, ValueError, TypeError) as error:
            report.append({"team": team, "branch": branch, "verdict": "UNKNOWN",
                           "instruction": "Inspect branch/API access and retry; never mark as FAIL or PASS without evidence",
                           "error": str(error)[:160]})
    return {"schema": 2, "scope": "read-only commit/CI preflight; job logs and independent QA still required",
            "teams": report, "completed_backlog_items": "not established",
            "next_action": "Inspect exact six job logs and task-specific independent QA before assigning PASS"}


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
