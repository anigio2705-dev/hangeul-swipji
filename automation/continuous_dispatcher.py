"""Fail-closed GitHub issue watchdog; a queue signal is NOT an AI worker.

The issue itself persists in GitHub. This process does not execute agents,
approve READY, or guarantee atomic creation against other producers.
"""
import json
import os
import re
import time
import urllib.request
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

API = "https://api.github.com"
MARKER = "[HS-AUTONOMOUS-WORK-REQUEST]"
PAGE_SIZE = 100
MAX_PAGES = 1000
STALE_SECONDS = 60 * 60
RETRYABLE = {429, 500, 502, 503, 504}


class QueueIntegrityError(RuntimeError):
    """Fail closed rather than create duplicate work."""


def request(path, token, method="GET", payload=None, *, opener=None, sleeper=time.sleep):
    if not token or not path.startswith("/repos/") or "://" in path:
        raise ValueError("invalid GitHub API request")
    opener = opener or urllib.request.urlopen
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        API + path, data=body, method=method,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28",
                 "User-Agent": "hangeul-swipji-watchdog"})
    for attempt in range(4):
        try:
            with opener(req, timeout=20) as response:
                return json.load(response)
        except HTTPError as error:
            # A normal 403 (missing issues:write) must never be retried or
            # silently treated as an empty queue. Rate-limit 403 is transient.
            headers = error.headers or {}
            limited = (error.code == 403 and
                       (headers.get("X-RateLimit-Remaining") == "0" or
                        headers.get("Retry-After") is not None))
            if (error.code not in RETRYABLE and not limited) or attempt == 3:
                raise
            wait = min(8, 2 ** attempt)
            try:
                wait = min(8, max(wait, int(headers.get("Retry-After", "0"))))
            except ValueError:
                pass
            sleeper(wait)


def list_open_issues(repo, token, *, fetch=request, max_pages=MAX_PAGES):
    """Exhaust ALL open issues, not just GitHub's first 100 (PRs included)."""
    if type(max_pages) is not int or max_pages < 1:
        raise ValueError("invalid page limit")
    items = []
    for page in range(1, max_pages + 1):
        result = fetch(
            "/repos/" + repo + "/issues?state=open&per_page=100&page=" + str(page),
            token)
        if not isinstance(result, list):
            raise QueueIntegrityError("GitHub issues response is not a list")
        items.extend(result)
        if len(result) < PAGE_SIZE:
            return items
    # A full last page is ambiguous. Never assume the queue is empty.
    raise QueueIntegrityError("issue pagination exceeded safety limit")


def pending(issues):
    # Pull requests also appear in GitHub issues API.
    return [i for i in issues if isinstance(i, dict)
            and "pull_request" not in i
            and i.get("title", "").startswith(MARKER)
            and i.get("state") == "open"]


def plan(issues, *, now=None):
    active = pending(issues)
    if len(active) > 1:
        return {"action": "blocked", "reason": "duplicate open work requests",
                "numbers": [i.get("number") for i in active]}
    if active:
        item = active[0]
        created = item.get("created_at")
        if created:
            try:
                age = ((now or datetime.now(timezone.utc)) -
                       datetime.fromisoformat(created.replace("Z", "+00:00"))).total_seconds()
            except (ValueError, TypeError):
                return {"action": "blocked", "reason": "invalid work request timestamp"}
            if age >= STALE_SECONDS:
                return {"action": "stale", "number": item.get("number"),
                        "reason": "unacknowledged work request older than 60 minutes"}
        return {"action": "wait", "number": item.get("number"),
                "reason": "existing unacknowledged work request"}
    return {"action": "create",
            "title": MARKER + " Central: inspect backlog and continue",
            "body": ("Central HQ: inspect Issue #34 and 160-item ledger; develop the next "
                     "eligible task; request separate team15 QA; central decides READY. "
                     "Support team only unblocks central. Close this request after "
                     "a verifiable run, not merely after reading. This issue is a "
                     "queue signal, NOT evidence that a ChatGPT worker started. "
                     "Do not deploy, pay, or change production data.")}


def valid_repo(repo):
    return isinstance(repo, str) and bool(re.fullmatch(
        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo))


def main():
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GH_TOKEN"]
    if not valid_repo(repo):
        raise ValueError("invalid repository")
    issues = list_open_issues(repo, token)
    result = plan(issues)
    print(json.dumps(result, ensure_ascii=False))
    if result["action"] in {"stale", "blocked"}:
        # A non-green Actions result is a visible alarm, not a READY claim.
        raise QueueIntegrityError(result["reason"])
    if result["action"] == "create" and os.environ.get("APPLY_QUEUE") == "true":
        # Second read narrows (but cannot eliminate) cross-workflow races.
        # Exactly-once requires a transactional external worker/queue.
        second = plan(list_open_issues(repo, token))
        if second["action"] != "create":
            print("CREATE_ABORTED_RECHECK=" + second["action"])
            return
        created = request("/repos/" + repo + "/issues", token, "POST",
                          {"title": result["title"], "body": result["body"]})
        print("QUEUED_ISSUE=" + str(created["number"]))
    elif result["action"] == "create":
        print("DRY_RUN: no issue created")


if __name__ == "__main__":
    main()
