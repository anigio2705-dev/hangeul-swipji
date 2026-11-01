"""Read-only GitHub CI polling fallback when webhook delivery is delayed.

This module only inserts verified CI-success *candidates* into the durable
outbox. It cannot request QA, grant READY, push, or deploy. The separate QA
dispatcher rechecks current PR SHA and every required CI check before POST.
"""
import json
import os
import re
import sqlite3
import urllib.request
from pathlib import Path

from issue_webhook_ingress import _persist_ci_qa_event
from qa_handoff_dispatcher import _trusted_db_path

REPO = "anigio2705-dev/hangeul-swipji"
MAX_PAGES = 5
PAGE_SIZE = 100


class PollIncomplete(RuntimeError):
    """Never represent a truncated or failed scan as complete."""


def github_get(path, token):
    if not path.startswith("/repos/" + REPO + "/") or not token:
        raise ValueError("unapproved GitHub API request")
    request = urllib.request.Request(
        "https://api.github.com" + path,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28",
                 "User-Agent": "hangeul-swipji-ci-fallback"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def poll_once(db_path, *, token, repo=REPO, fetch=github_get, pages=MAX_PAGES):
    if repo != REPO or not token or not isinstance(db_path, str):
        raise ValueError("unapproved polling environment")
    db_path = _trusted_db_path(db_path)
    if type(pages) is not int or not 1 <= pages <= MAX_PAGES:
        raise ValueError("invalid page limit")
    accepted = duplicates = skipped = 0
    for page in range(1, pages + 1):
        response = fetch(
            f"/repos/{repo}/actions/runs?event=pull_request&status=completed"
            f"&per_page=100&page={page}", token)
        runs = response.get("workflow_runs") if isinstance(response, dict) else None
        if not isinstance(runs, list) or len(runs) > PAGE_SIZE:
            raise PollIncomplete("invalid workflow runs response")
        for run in runs:
            if not isinstance(run, dict):
                raise PollIncomplete("malformed workflow run")
            prs = run.get("pull_requests")
            sha = run.get("head_sha")
            if (run.get("event") != "pull_request"
                    or run.get("status") != "completed"
                    or run.get("conclusion") != "success"
                    or not isinstance(prs, list) or len(prs) != 1
                    or not isinstance(prs[0], dict)
                    or type(prs[0].get("number")) is not int
                    or not isinstance(sha, str)
                    or not re.fullmatch(r"[0-9a-f]{40}", sha)
                    or not isinstance(run.get("head_repository"), dict)
                    or run["head_repository"].get("full_name") != repo):
                skipped += 1
                continue
            number = prs[0]["number"]
            pr = fetch(f"/repos/{repo}/pulls/{number}", token)
            if not isinstance(pr, dict):
                raise PollIncomplete("malformed PR response")
            head = pr.get("head")
            base = pr.get("base")
            if (not isinstance(head, dict) or not isinstance(base, dict)
                    or head.get("sha") != sha
                    or head.get("ref") != run.get("head_branch")
                    or not isinstance(head.get("repo"), dict)
                    or head["repo"].get("full_name") != repo
                    or not isinstance(base.get("ref"), str)
                    or base["ref"] in ("main", "master")
                    or pr.get("state") != "open" or pr.get("merged")
                    or not pr.get("draft")):
                skipped += 1
                continue
            event = {"action": "completed", "repository": {"full_name": repo},
                     "workflow_run": dict(run, pull_requests=[{
                         "number": number,
                         "base": {"ref": base["ref"]},
                         "head": {"ref": head["ref"], "sha": sha}}])}
            status, result = _persist_ci_qa_event(event, db_path=db_path)
            if status != 200:
                raise PollIncomplete("outbox rejected verified candidate")
            accepted += result == "qa_handoff_queued"
            duplicates += result == "duplicate_ci_event"
        if len(runs) < PAGE_SIZE:
            return {"queued": accepted, "duplicates": duplicates,
                    "skipped": skipped, "scan_complete": True}
    raise PollIncomplete("pagination limit reached; partial outbox is not full scan")


def main():
    for key in ("HS_DURABLE_WORKER_DB", "GITHUB_REPOSITORY", "CREDENTIALS_DIRECTORY"):
        if not os.environ.get(key):
            raise RuntimeError("missing polling environment")
    credential = Path(os.environ["CREDENTIALS_DIRECTORY"]) / "gh_token"
    if credential.is_symlink() or not credential.is_file():
        raise RuntimeError("missing protected credential")
    result = poll_once(os.environ["HS_DURABLE_WORKER_DB"],
                       token=credential.read_text(encoding="utf-8").strip(),
                       repo=os.environ["GITHUB_REPOSITORY"])
    print("CI_POLL_FALLBACK=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
