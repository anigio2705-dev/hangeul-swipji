"""Signed GitHub issues webhook -> existing durable SQLite work queue.

Infrastructure support only. This does not invoke Codex, approve QA/READY,
perform a Git push, or claim 24-hour availability. Bind to loopback behind a
separately managed HTTPS reverse proxy; keep the HMAC secret off the agent.
"""
import fcntl
import hashlib
import hmac
import json
import os
import re
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from continuous_dispatcher import MARKER
from work_request_worker import DurableWorkStore

MAX_BODY = 262144
DELIVERY_ID = re.compile(r"^[0-9a-fA-F-]{36}$")
ACTIONS = {"opened", "reopened", "edited", "closed"}


class InvalidDelivery(ValueError):
    pass


def process_delivery(body, headers, *, secret, repository, db_path):
    """Return (HTTP status, result). 2xx only after durable acknowledgement."""
    if not secret or not repository or not db_path:
        raise RuntimeError("webhook environment incomplete")
    if len(body) > MAX_BODY:
        raise InvalidDelivery("oversized payload")
    signature = headers.get("X-Hub-Signature-256", "")
    if not isinstance(signature, str) or not re.fullmatch(r"sha256=[0-9a-fA-F]{64}", signature):
        raise InvalidDelivery("missing signature")
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature.lower(), expected):
        raise InvalidDelivery("signature mismatch")
    delivery_id = headers.get("X-GitHub-Delivery", "")
    if not isinstance(delivery_id, str) or not DELIVERY_ID.fullmatch(delivery_id):
        raise InvalidDelivery("invalid delivery id")
    try:
        event = json.loads(body)
    except (ValueError, UnicodeError) as exc:
        raise InvalidDelivery("invalid JSON") from exc
    if (not isinstance(event, dict) or not isinstance(event.get("repository"), dict)
            or event["repository"].get("full_name") != repository):
        raise InvalidDelivery("repository mismatch")
    if headers.get("X-GitHub-Event") == "workflow_run":
        return _persist_ci_qa_event(event, db_path=db_path)
    if headers.get("X-GitHub-Event") != "issues" or event.get("action") not in ACTIONS:
        return 202, "ignored_event"
    issue = event.get("issue")
    if (not isinstance(issue, dict) or "pull_request" in issue
            or type(issue.get("number")) is not int
            or issue["number"] < 1 or not isinstance(issue.get("title"), str)
            or not issue["title"].startswith(MARKER)):
        return 202, "ignored_issue"
    if event["action"] != "closed" and issue.get("state") != "open":
        return 202, "ignored_issue"
    if event["action"] == "closed" and issue.get("state") != "closed":
        raise InvalidDelivery("inconsistent close event")
    # Serialize concurrent webhook handlers. The 30s polling sync is a separate
    # reconciliation path and must still fail closed on multiple open issues.
    lock_fd = os.open(db_path + ".webhook.lock", os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(lock_fd, fcntl.LOCK_EX)
    store = None
    try:
        store = DurableWorkStore(db_path)
        store.db.execute("""CREATE TABLE IF NOT EXISTS webhook_deliveries (
            delivery_id TEXT PRIMARY KEY, issue INTEGER NOT NULL,
            received_at INTEGER NOT NULL)""")
        if store.db.execute("SELECT 1 FROM webhook_deliveries WHERE delivery_id=?",
                            (delivery_id,)).fetchone():
            return 200, "duplicate_delivery"
        if event["action"] == "closed":
            store.db.execute("BEGIN IMMEDIATE")
            try:
                store.db.execute("""UPDATE work SET status='CANCELLED',
                    lease_owner=NULL, lease_until=0 WHERE issue=?
                    AND status IN ('PENDING','LEASED')""", (issue["number"],))
                store.db.execute("INSERT OR IGNORE INTO webhook_deliveries VALUES (?,?,?)",
                                 (delivery_id, issue["number"], int(time.time())))
                store.db.execute("COMMIT")
            except Exception:
                store.db.execute("ROLLBACK")
                raise
            return 200, "durably_cancelled"
        # Never introduce two distinct active work requests through this path.
        # A full GitHub scan by the fallback sync is still authoritative.
        other = store.db.execute("""SELECT issue FROM work WHERE issue != ?
            AND status IN ('PENDING','LEASED') LIMIT 1""", (issue["number"],)).fetchone()
        if other:
            return 409, "multiple_active_requests"
        store.ingest(issue)
        store.db.execute("INSERT OR IGNORE INTO webhook_deliveries VALUES (?,?,?)",
                         (delivery_id, issue["number"], int(time.time())))
        return 200, "durably_ingested"
    finally:
        if store is not None:
            store.close()
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def _persist_ci_qa_event(event, *, db_path):
    """Persist CI-success candidates for a separate authenticated B-QA dispatcher.

    This is an OUTBOX, not a QA request, QA_PASS, READY or authorization to
    start the next product task. The dispatcher must re-fetch PR HEAD and CI
    status from GitHub before notifying B. No GitHub credential is needed here.
    """
    run = event.get("workflow_run")
    if (event.get("action") != "completed" or not isinstance(run, dict)
            or run.get("conclusion") != "success"
            or run.get("event") != "pull_request"):
        return 202, "ignored_workflow"
    repo = event["repository"]["full_name"]
    source = run.get("head_repository")
    prs = run.get("pull_requests")
    if (not isinstance(source, dict) or source.get("full_name") != repo
            or not isinstance(prs, list) or len(prs) != 1
            or not isinstance(prs[0], dict)):
        return 202, "ignored_workflow"
    pr = prs[0]
    sha = run.get("head_sha")
    branch = run.get("head_branch")
    base = pr.get("base")
    head = pr.get("head")
    run_id = run.get("id")
    attempt = run.get("run_attempt")
    if (type(run_id) is not int or run_id <= 0
            or type(attempt) is not int or attempt <= 0
            or type(pr.get("number")) is not int or pr["number"] <= 0
            or not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha)
            or not isinstance(branch, str) or not branch.startswith(
                ("work/", "automation/", "agent/", "support/"))
            or not isinstance(base, dict) or not isinstance(base.get("ref"), str)
            or base["ref"] in ("main", "master")
            or not isinstance(head, dict)
            or head.get("ref") != branch):
        return 202, "ignored_workflow"
    # Some workflow_run payloads omit the PR head SHA. If present it must
    # agree; regardless, the downstream dispatcher MUST revalidate via API.
    if head.get("sha") is not None and head["sha"] != sha:
        raise InvalidDelivery("workflow PR SHA mismatch")
    connection = sqlite3.connect(db_path, timeout=15, isolation_level=None)
    try:
        connection.execute("PRAGMA busy_timeout=15000")
        connection.execute("""CREATE TABLE IF NOT EXISTS ci_qa_outbox (
            run_id INTEGER NOT NULL, run_attempt INTEGER NOT NULL,
            pr_number INTEGER NOT NULL, head_sha TEXT NOT NULL,
            branch TEXT NOT NULL, base_ref TEXT NOT NULL,
            ci_completed_at TEXT NOT NULL, received_at INTEGER NOT NULL,
            processing_at INTEGER NOT NULL DEFAULT 0,
            qa_requested_at INTEGER NOT NULL DEFAULT 0,
            state TEXT NOT NULL DEFAULT 'PENDING_B_QA_REQUEST',
            PRIMARY KEY (run_id,run_attempt))""")
        connection.execute("BEGIN IMMEDIATE")
        try:
            old = connection.execute(
                "SELECT pr_number,head_sha,branch,base_ref FROM ci_qa_outbox "
                "WHERE run_id=? AND run_attempt=?", (run_id, attempt)).fetchone()
            record = (pr["number"], sha, branch, base["ref"])
            if old and tuple(old) != record:
                raise InvalidDelivery("conflicting CI event replay")
            if not old:
                connection.execute(
                    """INSERT INTO ci_qa_outbox
                    (run_id,run_attempt,pr_number,head_sha,branch,base_ref,
                     ci_completed_at,received_at)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (run_id, attempt, *record,
                     str(run.get("updated_at") or ""), int(time.time())))
            connection.execute("COMMIT")
            return (200, "duplicate_ci_event") if old else (200, "qa_handoff_queued")
        except BaseException:
            connection.execute("ROLLBACK")
            raise
    finally:
        connection.close()


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/github/issues":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            self.send_error(400)
            return
        if length < 0 or length > MAX_BODY:
            self.send_error(413)
            return
        body = self.rfile.read(length)
        if len(body) != length:
            self.send_error(400)
            return
        try:
            status, result = process_delivery(
                body, self.headers, secret=os.environ["HS_WEBHOOK_SECRET"],
                repository=os.environ["GITHUB_REPOSITORY"],
                db_path=os.environ["HS_DURABLE_WORKER_DB"])
        except InvalidDelivery:
            status, result = 403, "invalid_delivery"
        except (sqlite3.Error, OSError, RuntimeError, KeyError):
            # Fail closed: do not acknowledge undurable work as successful.
            status, result = 503, "queue_unavailable"
        output = json.dumps({"result": result}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(output)))
        self.end_headers()
        self.wfile.write(output)

    def log_message(self, fmt, *args):
        # Never log request body, signature, secrets, or query parameters.
        pass


def main():
    for key in ("HS_WEBHOOK_SECRET", "GITHUB_REPOSITORY", "HS_DURABLE_WORKER_DB"):
        if not os.environ.get(key):
            raise RuntimeError("missing required webhook environment")
    if len(os.environ["HS_WEBHOOK_SECRET"]) < 32:
        raise RuntimeError("webhook secret must be at least 32 characters")
    if not os.environ["HS_DURABLE_WORKER_DB"].startswith("/var/lib/hangeul-swipji/"):
        raise RuntimeError("webhook DB must be on the mounted durable volume")
    ThreadingHTTPServer(("127.0.0.1", 8778), Handler).serve_forever()


if __name__ == "__main__":
    main()
