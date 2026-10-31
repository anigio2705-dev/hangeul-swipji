"""Fail-closed CI_SUCCESS -> B/15-team exact-SHA QA request outbox dispatcher.

Only a separate trusted controller host may run this module. A GitHub comment
requests QA; it NEVER represents QA_PASS, A READY, or next-task authorization.
No secrets are printed or passed to an AI-controlled subprocess.
"""
import json
import os
import sqlite3
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"
DB_ROOT = "/var/lib/hangeul-swipji/"


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


def _existing_comment(repo, issue_number, token, marker, legacy_marker=None):
    # Search the full thread. Never risk an ambiguous duplicate POST because
    # the first page omitted a comment from a long-running issue.
    for page in range(1, 21):
        rows = _request(
            f"/repos/{repo}/issues/{issue_number}/comments?per_page=100&page={page}",
            token)
        if not isinstance(rows, list):
            raise ValueError("malformed issue comments")
        for item in rows:
            body = str(item.get("body", ""))
            if marker in body:
                return item.get("html_url", "")
            # Before run/attempt markers existed, attempt 1 used a bare
            # PR/SHA marker. Match the *whole line* only; never confuse a
            # newer attempt-specific marker with the legacy form.
            if legacy_marker and legacy_marker in body.splitlines():
                return item.get("html_url", "")
        if len(rows) < 100:
            return None
    raise ValueError("comment pagination exceeded safe limit")



# SQLite migration is additive: existing CI webhook rows retain run/attempt/SHA.
# Every network operation runs outside the SQLite write transaction.
MAX_ATTEMPTS = 12
LEASE_SECONDS = 90


def _schema(db):
    cols = {row[1] for row in db.execute("PRAGMA table_info(ci_qa_outbox)")}
    if not cols:
        raise ValueError("CI outbox missing; webhook ingestion must initialize it")
    for name, ddl in (
        ("next_attempt_at", "INTEGER NOT NULL DEFAULT 0"),
        ("attempts", "INTEGER NOT NULL DEFAULT 0"),
        ("lease_token", "TEXT NOT NULL DEFAULT ''"),
        ("lease_until", "INTEGER NOT NULL DEFAULT 0"),
        ("post_started_at", "INTEGER NOT NULL DEFAULT 0"),
        ("last_error", "TEXT NOT NULL DEFAULT ''"),
    ):
        if name not in cols:
            db.execute("ALTER TABLE ci_qa_outbox ADD COLUMN " + name + " " + ddl)
    db.execute("CREATE INDEX IF NOT EXISTS ci_qa_due ON ci_qa_outbox "
               "(state,next_attempt_at,received_at)")


def _claim(db, now):
    """Atomic per-item claim; delayed/ambiguous rows cannot block fresh work."""
    db.execute("BEGIN IMMEDIATE")
    try:
        _schema(db)
        row = db.execute(
            """SELECT run_id,run_attempt,pr_number,head_sha,branch,base_ref,
                      state,ci_completed_at,post_started_at,attempts
               FROM ci_qa_outbox
               WHERE ((state IN ('PENDING_B_QA_REQUEST','RETRY_WAIT','AMBIGUOUS_POST')
                       AND next_attempt_at<=?)
                   OR (state IN ('CLAIMED','POST_IN_FLIGHT') AND lease_until<=?))
               ORDER BY next_attempt_at,received_at,run_id,run_attempt LIMIT 1""",
            (now, now)).fetchone()
        if row is None:
            db.execute("COMMIT")
            return None
        token = uuid.uuid4().hex
        db.execute(
            """UPDATE ci_qa_outbox SET state='CLAIMED',lease_token=?,
                   lease_until=?,processing_at=?
               WHERE run_id=? AND run_attempt=?""",
            (token, now + LEASE_SECONDS, now, row[0], row[1]))
        db.execute("COMMIT")
        return (*row, token)
    except BaseException:
        db.execute("ROLLBACK")
        raise


def _finish(db, row, token, state, now, *, error="", requested=False,
            retry=False):
    """Fenced transition: a stale worker cannot overwrite a newer claim."""
    run_id, attempt = row[:2]
    attempts = row[9] + (1 if retry else 0)
    if retry and attempts >= MAX_ATTEMPTS:
        state = "DEAD_LETTER"
    delay = min(3600, 15 * (2 ** min(attempts, 8))) if retry else 0
    db.execute("BEGIN IMMEDIATE")
    try:
        updated = db.execute(
            """UPDATE ci_qa_outbox SET state=?,next_attempt_at=?,
                attempts=?,lease_token='',lease_until=0,last_error=?,
                qa_requested_at=CASE WHEN ? THEN ? ELSE qa_requested_at END
               WHERE run_id=? AND run_attempt=? AND lease_token=?
                 AND state='CLAIMED'""",
            (state, now + delay, attempts, error[:120], int(requested), now,
             run_id, attempt, token)).rowcount
        db.execute("COMMIT")
        return updated == 1
    except BaseException:
        db.execute("ROLLBACK")
        raise


def _post_boundary(db, row, token, now):
    """Persist POST_IN_FLIGHT before sending any byte; crash is ambiguous."""
    db.execute("BEGIN IMMEDIATE")
    try:
        updated = db.execute(
            """UPDATE ci_qa_outbox SET state='POST_IN_FLIGHT',
                post_started_at=?,lease_until=?
               WHERE run_id=? AND run_attempt=? AND lease_token=?
                 AND state='CLAIMED' AND post_started_at=0""",
            (now, now + LEASE_SECONDS, row[0], row[1], token)).rowcount
        db.execute("COMMIT")
        return updated == 1
    except BaseException:
        db.execute("ROLLBACK")
        raise


def _finish_post(db, row, token, state, now, *, error="", requested=False):
    """Only the POST owner can complete or quarantine an uncertain send."""
    db.execute("BEGIN IMMEDIATE")
    try:
        updated = db.execute(
            """UPDATE ci_qa_outbox SET state=?,next_attempt_at=?,
                attempts=attempts+1,lease_token='',lease_until=0,last_error=?,
                qa_requested_at=CASE WHEN ? THEN ? ELSE qa_requested_at END
               WHERE run_id=? AND run_attempt=? AND lease_token=?
                 AND state='POST_IN_FLIGHT'""",
            (state, now + (60 if state == 'AMBIGUOUS_POST' else 0),
             error[:120], int(requested), now, row[0], row[1], token)).rowcount
        db.execute("COMMIT")
        return updated == 1
    except BaseException:
        db.execute("ROLLBACK")
        raise


def dispatch_once(db_path, *, token, repo, issue_number=34, now=None):
    """One eligible exact-SHA handoff. Unknown POST is reconcile-only."""
    if not token or repo != "anigio2705-dev/hangeul-swipji":
        raise ValueError("missing controller token or unapproved repo")
    if not db_path.startswith(DB_ROOT):
        raise ValueError("expected mounted durable database")
    now = int(time.time() if now is None else now)
    db = sqlite3.connect(db_path, timeout=15, isolation_level=None)
    try:
        db.execute("PRAGMA busy_timeout=15000")
        row = _claim(db, now)
        if row is None:
            return "IDLE"
        run_id, attempt, pr, sha, branch, base, previous, ci_at, post_at, tries, lease = row
        legacy_marker = f"HS_B_QA_HANDOFF pr={pr} sha={sha}"
        marker = f"{legacy_marker} run={run_id} attempt={attempt}"
        uncertain = bool(post_at) or previous in ("AMBIGUOUS_POST", "POST_IN_FLIGHT")
        # Validate before even reading remote data. Never post on malformed rows.
        if (type(pr) is not int or pr < 1 or type(run_id) is not int
                or type(attempt) is not int or attempt < 1
                or not isinstance(sha, str) or len(sha) != 40
                or any(c not in "0123456789abcdef" for c in sha)):
            _finish(db, row, lease, "DEAD_LETTER", now, error="invalid identity")
            return "DEAD_LETTER"
        try:
            run = _request(f"/repos/{repo}/actions/runs/{run_id}", token)
            pull = _request(f"/repos/{repo}/pulls/{pr}", token)
            run_prs = run.get("pull_requests")
            run_repo = run.get("head_repository")
            if (not isinstance(run_prs, list)
                    or not any(isinstance(item, dict)
                               and item.get("number") == pr for item in run_prs)
                    or not isinstance(run_repo, dict)
                    or run_repo.get("full_name") != repo
                    or run.get("head_sha") != sha or run.get("run_attempt") != attempt
                    or run.get("status") != "completed"
                    or run.get("conclusion") != "success"
                    or run.get("event") != "pull_request"
                    or pull.get("head", {}).get("sha") != sha
                    or pull.get("head", {}).get("ref") != branch
                    or pull.get("base", {}).get("ref") != base
                    or pull.get("merged") or pull.get("state") != "open"
                    or not pull.get("draft")):
                _finish(db, row, lease, "STALE_OR_UNVERIFIED", now)
                return "STALE_OR_UNVERIFIED"
            checks = _request(
                f"/repos/{repo}/commits/{sha}/check-runs?per_page=100", token)
            rows = checks.get("check_runs") if isinstance(checks, dict) else None
            if (not isinstance(rows, list) or not rows
                    or type(checks.get("total_count")) is not int
                    or checks["total_count"] != len(rows)
                    or any(item.get("status") != "completed"
                           or item.get("conclusion") != "success" for item in rows)):
                _finish(db, row, lease, "RETRY_WAIT", now,
                        error="CI_NOT_COMPLETE", retry=True)
                return "CI_NOT_COMPLETE"
            found = _existing_comment(
                repo, issue_number, token, marker,
                legacy_marker if attempt == 1 else None)
            if found is not None:
                _finish(db, row, lease, "B_QA_REQUESTED", now, requested=True)
                return "RECONCILED"
            if uncertain:
                # A prior POST might have succeeded despite 503/timeout/crash.
                # Reconcile by marker only. Never replay the POST automatically.
                _finish(db, row, lease, "AMBIGUOUS_POST", now,
                        error="POST_OUTCOME_UNKNOWN", retry=True)
                return "AMBIGUOUS_POST"
            if not _post_boundary(db, row, lease, now):
                return "LEASE_LOST"
            message = (
                f"[신임 C 자동 CI→B QA 요청] {marker}\\n"
                f"PR #{pr} 정확 HEAD {sha} / CI run {run_id} SUCCESS. "
                "B/15팀은 이 SHA만 독립 QA_PASS/FAIL 검증하십시오. "
                "CI_PASS는 QA_PASS나 A READY가 아니며 자동 병합·운영 배포 금지. "
                f"CI completed_at={ci_at or 'UNKNOWN'}; QA request at={now} epoch."
            )
            try:
                _request(f"/repos/{repo}/issues/{issue_number}/comments",
                         token, {"body": message})
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                    ValueError, KeyError, TypeError, OSError):
                _finish_post(db, row, lease, "AMBIGUOUS_POST", now,
                             error="POST_RESULT_UNKNOWN")
                return "AMBIGUOUS_POST"
            _finish_post(db, row, lease, "B_QA_REQUESTED", now, requested=True)
            return "B_QA_REQUESTED"
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                ValueError, KeyError, TypeError, OSError):
            # Read-only failure: safe retry unless an earlier POST began.
            if uncertain:
                _finish(db, row, lease, "AMBIGUOUS_POST", now,
                        error="RECONCILE_GET_FAILED", retry=True)
                return "AMBIGUOUS_POST"
            _finish(db, row, lease, "RETRY_WAIT", now,
                    error="PRE_POST_GET_FAILED", retry=True)
            return "RETRY_WAIT"
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
