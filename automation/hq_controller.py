"""Bounded HQ controller: ten real audit/decision cycles and at most one developer dispatch.

Never merges, deploys, touches main, or claims completion from CI alone.
"""
import json
import os
import time
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from hq_six_team_audit import audit, REPO

BRANCH = "automation/hq-pilot-13-14-15-20261029"
WORKFLOW = "hq-six-developers.yml"

def request(path, token, method="GET", payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request("https://api.github.com/repos/" + REPO + path, data=data,
                  method=method, headers={
                      "Authorization": "Bearer " + token,
                      "Accept": "application/vnd.github+json",
                      "Content-Type": "application/json",
                      "User-Agent": "hq-controller"})
    with urlopen(req, timeout=25) as response:
        raw = response.read()
        return json.loads(raw) if raw else {}

def workflow_runs(token):
    data = request("/actions/workflows/" + WORKFLOW + "/runs?branch=" + BRANCH + "&per_page=30", token)
    return data.get("workflow_runs", [])

def decision(report, runs, already_dispatched):
    active = [r for r in runs if r.get("status") in ("queued", "in_progress", "waiting", "pending")]
    blocked = [x for x in report["teams"] if x["verdict"] == "BLOCKED"]
    rework = [x for x in report["teams"] if x["verdict"] == "REWORK"]
    review = [x for x in report["teams"] if x["verdict"] == "REVIEW"]
    if blocked:
        return "ESCALATE", "Team branch/API access blocked; inspect before dispatch"
    if active:
        return "WAIT", "Existing six-team development still running"
    if already_dispatched:
        return "VERIFY", "Development was dispatched once; wait for new results before re-dispatch"
    if rework:
        return "DISPATCH", "Start one bounded six-team development run; require specific CI repair evidence"
    if review:
        return "REVIEW", "Passing CI requires backlog-specific integration review; do not manufacture more commits"
    return "DISPATCH", "Start one bounded six-team run to collect real development evidence"

def main():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("Missing GitHub token")
    history, dispatched = [], False
    cycles = max(1, min(10, int(os.environ.get("HQ_CYCLES", "10"))))
    delay = max(0, min(30, int(os.environ.get("HQ_CYCLE_DELAY", "8"))))
    for cycle in range(1, cycles + 1):
        entry = {"cycle": cycle, "at": datetime.now(timezone.utc).isoformat()}
        try:
            report = audit(token)
            runs = workflow_runs(token)
            verdict, reason = decision(report, runs, dispatched)
            entry.update({"verdict": verdict, "reason": reason,
                          "team_verdicts": {t["team"]: t["verdict"] for t in report["teams"]},
                          "active_developer_runs": sum(r.get("status") != "completed" for r in runs),
                          "latest_developer_run": runs[0]["html_url"] if runs else None})
            if verdict == "DISPATCH" and os.environ.get("HQ_ALLOW_DISPATCH") == "true":
                request("/actions/workflows/" + WORKFLOW + "/dispatches", token,
                        method="POST", payload={"ref": BRANCH, "inputs": {"chain_depth": "0"}})
                dispatched = True
                entry["dispatched"] = True
        except (HTTPError, ValueError, KeyError, TimeoutError) as exc:
            entry.update({"verdict": "ERROR", "reason": str(exc)[:250]})
        history.append(entry)
        print(json.dumps(entry, ensure_ascii=False), flush=True)
        if cycle < cycles:
            time.sleep(delay)
    result = {"schema": 1, "cycles": history, "dispatched": dispatched,
              "safety": "isolated branch only; no merge, deployment, payment or false completion",
              "limitation": "Ten controller decisions are not ten completed development tasks"}
    with open("hq-controller-report.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    if all(x["verdict"] == "ERROR" for x in history):
        raise SystemExit("All ten controller cycles failed")

if __name__ == "__main__":
    main()
