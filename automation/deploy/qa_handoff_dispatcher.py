"""Fail-closed CI_SUCCESS -> B/15-team exact-SHA QA request outbox dispatcher.

Only a separate trusted controller host may run this module. A GitHub comment
requests QA; it NEVER represents QA_PASS, A READY, or next-task authorization.
No secrets are printed or passed to an AI-controlled subprocess.
"""
import json
import os
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"


def _request(path, token, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        API + path, data=data, method="POST" if data is not None else "GET",
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def _existing_comment(repo, issue_number, token, marker):
    # Search the full thread. Never risk an ambiguous duplicate POST because
    # the first page omitted a comment from a long-running issue.
    for page in range(1, 21):
        rows = _request(
            f"/repos/{repo}/issues/{issue_number}/comments?per_page=100&page={page}",
            token)
        if not isinstance(rows, list):
            raise ValueError("malformed issue comments")
        for item in rows:
            if marker in str(item.get("body", "")):
                return item.get("html_url", "")
        if len(rows) < 100:
            return None
    raise ValueError("comment pagination exceeded safe limit")


def _mark(db, run_id, attempt, state, *, requested_at=None):
    db.execute("BEGIN IMMEDIATE")
    try:
        db.execute(
            "UPDATE ci_qa_outbox SET state=?, qa_requested_at=COALESCE(?,qa_requested_at) "
            "WHERE run_id=? AND run_attempt=?",
            (state, requested_at, run_id, attempt))
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise


def dispatch_once(db_path, *, token, repo, issue_number=34, now=None):
    """Attempt one durable handoff. Unknown POST outcome is never auto-retried."""
    if not token or repo != "anigio2705-dev/hangeul-swipji":
        raise ValueError("missing controller token or unapproved repo")
    if not db_path.startswith("/var/lib/hangeul-swipji/"):
        raise ValueError("expected mounted durable database")
    now = int(time.time() if now is None else now)
    db = sqlite3.connect(db_path, timeout=15, isolation_level=None)
    try:
        db.execute("PRAGMA busy_timeout=15000")
        db.execute("BEGIN IMMEDIATE")
        try:
            row = db.execute(
                """SELECT run_id,run_attempt,pr_number,head_sha,branch,base_ref,
                          state,processing_at,ci_completed_at
                   FROM ci_qa_outbox
                   WHERE state IN ('PENDING_B_QA_REQUEST','SENDING','AMBIGUOUS_POST')
                   ORDER BY received_at,run_id LIMIT 1""").fetchone()
            if row is None:
                db.execute("COMMIT")
                return "IDLE"
            run_id, attempt, pr, sha, branch, base, state, touched, ci_at = row
            if state == "SENDING" and now - touched < 120:
                db.execute("COMMIT")
                return "IN_FLIGHT"
            db.execute(
                "UPDATE ci_qa_outbox SET state='SENDING',processing_at=? "
                "WHERE run_id=? AND run_attempt=?",
                (now, run_id, attempt))
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise

        marker = f"HS_B_QA_HANDOFF run={run_id} attempt={attempt} sha={sha}"
        try:
            # Both immutable CI run identity and CURRENT PR HEAD must match.
            # A newer PR commit invalidates this old handoff.
            run = _request(f"/repos/{repo}/actions/runs/{run_id}", token)
            pull = _request(f"/repos/{repo}/pulls/{pr}", token)
            if (run.get("head_sha") != sha or run.get("run_attempt") != attempt
                    or run.get("status") != "completed"
                    or run.get("conclusion") != "success"
                    or run.get("event") != "pull_request"
                    or pull.get("head", {}).get("sha") != sha
                    or pull.get("head", {}).get("ref") != branch
                    or pull.get("base", {}).get("ref") != base
                    or pull.get("merged") or pull.get("state") != "open"
                    or not pull.get("draft")):
                _mark(db, run_id, attempt, "STALE_OR_UNVERIFIED")
                return "STALE_OR_UNVERIFIED"
            found = _existing_comment(repo, issue_number, token, marker)
            if found is not None:
                _mark(db, run_id, attempt, "B_QA_REQUESTED", requested_at=now)
                return "RECONCILED"
            if state != "PENDING_B_QA_REQUEST":
                # A crash/HTTP 503 after POST could have delivered the comment.
                # Never blindly replay a POST even if GET cannot see it yet.
                _mark(db, run_id, attempt, "AMBIGUOUS_POST")
                return "AMBIGUOUS_POST"
            message = (
                f"[신임 C 자동 CI→B QA 요청] {marker}\n"
                f"PR #{pr} 정확 HEAD {sha} / CI run {run_id} SUCCESS. "
                "B/15팀은 이 SHA만 독립 QA_PASS/FAIL 검증하십시오. "
                "CI_PASS는 QA_PASS나 A READY가 아니며 자동 병합·운영 배포 금지. "
                f"CI completed_at={ci_at or 'UNKNOWN'}; QA request at={now} epoch."
            )
            _request(f"/repos/{repo}/issues/{issue_number}/comments",
                     token, {"body": message})
            _mark(db, run_id, attempt, "B_QA_REQUESTED", requested_at=now)
            return "B_QA_REQUESTED"
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                ValueError, KeyError, TypeError, OSError):
            _mark(db, run_id, attempt, "AMBIGUOUS_POST")
            return "AMBIGUOUS_POST"
    finally:
        db.close()


def main():
    # systemd LoadCredential supplies the GitHub token as a protected file,
    # never as a GH_TOKEN environment variable inherited by an AI subprocess.
    for key in ("HS_DURABLE_WORKER_DB", "GITHUB_REPOSITORY",
                "CREDENTIALS_DIRECTORY"):
        if not os.environ.get(key):
            raise SystemExit("missing isolated dispatcher configuration")
    from pathlib import Path
    credentials = Path(os.environ["CREDENTIALS_DIRECTORY"]) / "gh_token"
    if credentials.is_symlink() or not credentials.is_file():
        raise SystemExit("missing protected GitHub credential")
    token = credentials.read_text(encoding="utf-8").strip()
    if not token:
        raise SystemExit("empty protected GitHub credential")
    result = dispatch_once(
        os.environ["HS_DURABLE_WORKER_DB"],
        token=token, repo=os.environ["GITHUB_REPOSITORY"])
    print("QA_OUTBOX_RESULT=" + result)
    if result in ("AMBIGUOUS_POST", "STALE_OR_UNVERIFIED"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
