"""SQLite-backed handoff for an EXTERNAL authenticated AI worker (not an AI runner).

A durable volume and a real agent adapter are required. No ChatGPT API call,
GitHub issue closure, READY approval, or production change happens here.
Lease expiry enables at-least-once delivery; workers must make side effects
idempotent and recheck the exact SHA before any future execution.
"""
import json
import os
import sqlite3
import time
import uuid

from continuous_dispatcher import MARKER, QueueIntegrityError


class DurableWorkStore:
    def __init__(self, path):
        if not path:
            raise ValueError("durable DB path required")
        self.db = sqlite3.connect(path, timeout=15, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=15000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS work (
            issue INTEGER PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL,
            lease_owner TEXT, lease_until INTEGER NOT NULL DEFAULT 0,
            attempts INTEGER NOT NULL DEFAULT 0, retry_after INTEGER NOT NULL DEFAULT 0,
            proof TEXT, created_at INTEGER NOT NULL)""")

    def close(self):
        self.db.close()

    def ingest(self, issue, *, now=None):
        if not isinstance(issue, dict) or "pull_request" in issue or issue.get("state") != "open":
            raise ValueError("not a work issue")
        number = issue.get("number")
        title = issue.get("title")
        if type(number) is not int or number < 1 or not isinstance(title, str) or not title.startswith(MARKER):
            raise ValueError("invalid work issue")
        now = int(time.time() if now is None else now)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT title FROM work WHERE issue=?", (number,)).fetchone()
            if row and row[0] != title:
                raise QueueIntegrityError("issue number replay with changed title")
            if not row:
                self.db.execute(
                    "INSERT INTO work(issue,title,status,created_at) VALUES(?,?,'PENDING',?)",
                    (number, title, now))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def claim(self, owner, *, now=None, lease_seconds=300):
        if not isinstance(owner, str) or not owner.strip() or not 30 <= lease_seconds <= 3600:
            raise ValueError("invalid worker lease")
        now = int(time.time() if now is None else now)
        lease_identity = owner + ':' + uuid.uuid4().hex
        self.db.execute("BEGIN IMMEDIATE")
        try:
            # Expired leases are eligible for redelivery, not proof of completion.
            # A worker crash after the final allowed attempt must not leave
            # an expired LEASED row that looks active forever.
            self.db.execute("""UPDATE work SET status='BLOCKED',lease_owner=NULL
                WHERE status='LEASED' AND lease_until<=? AND attempts>=3""", (now,))
            row = self.db.execute("""SELECT issue,title,attempts FROM work
                WHERE ((status='PENDING' AND retry_after<=?)
                       OR (status='LEASED' AND lease_until<=?))
                  AND attempts<3
                ORDER BY created_at,issue LIMIT 1""", (now, now)).fetchone()
            if not row:
                self.db.execute("COMMIT")
                return None
            number, title, attempts = row
            self.db.execute("""UPDATE work SET status='LEASED',lease_owner=?,
                lease_until=?,attempts=? WHERE issue=?""",
                (lease_identity, now + lease_seconds, attempts + 1, number))
            self.db.execute("COMMIT")
            return {"issue": number, "title": title, "owner": lease_identity,
                    "attempt": attempts + 1, "lease_until": now + lease_seconds}
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def heartbeat(self, issue, owner, *, now=None, lease_seconds=300):
        now = int(time.time() if now is None else now)
        if not 30 <= lease_seconds <= 3600:
            raise ValueError("invalid lease")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            updated = self.db.execute("""UPDATE work SET lease_until=?
                WHERE issue=? AND status='LEASED' AND lease_owner=?
                AND lease_until>?""", (now + lease_seconds, issue, owner, now)).rowcount
            self.db.execute("COMMIT")
            return updated == 1
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def finish(self, issue, owner, proof, *, now=None):
        # A worker's claim is only a REPORT; independent QA is still required.
        if not isinstance(proof, str) or len(proof.strip()) < 10:
            raise ValueError("proof reference required")
        now = int(time.time() if now is None else now)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            updated = self.db.execute("""UPDATE work SET status='REPORTED',
                proof=?,lease_until=0 WHERE issue=? AND status='LEASED'
                AND lease_owner=? AND lease_until>?""",
                (proof, issue, owner, now)).rowcount
            self.db.execute("COMMIT")
            return updated == 1
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def fail(self, issue, owner, *, now=None):
        now = int(time.time() if now is None else now)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("""SELECT attempts FROM work
                WHERE issue=? AND status='LEASED' AND lease_owner=?
                AND lease_until>?""", (issue, owner, now)).fetchone()
            if not row:
                self.db.execute("COMMIT")
                return False
            attempts = row[0]
            status = "BLOCKED" if attempts >= 3 else "PENDING"
            self.db.execute("""UPDATE work SET status=?,lease_owner=NULL,
                lease_until=0,retry_after=? WHERE issue=?""",
                (status, now + min(3600, 60 * 2 ** (attempts - 1)), issue))
            self.db.execute("COMMIT")
            return True
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def reconcile_open(self, open_numbers):
        """Cancel queued work absent from a complete, successful GitHub open-issue scan."""
        if not isinstance(open_numbers, set) or any(type(n) is not int for n in open_numbers):
            raise ValueError("complete open issue number set required")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            rows = self.db.execute("SELECT issue FROM work WHERE status IN ('PENDING','LEASED')").fetchall()
            for (number,) in rows:
                if number not in open_numbers:
                    self.db.execute("""UPDATE work SET status='CANCELLED',lease_owner=NULL,
                        lease_until=0 WHERE issue=? AND status IN ('PENDING','LEASED')""", (number,))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def fenced_remote_write(self, issue, owner, callback, *, minimum_seconds=150):
        """Serialize remote side effects with durable cancellation/lease transfer.

        The SQLite BEGIN IMMEDIATE transaction is the write fence: reconcile_open,
        claim, fail, and finish cannot commit while this callback runs. A
        cancellation committed first rejects the write. A cancellation arriving
        during a write must wait for the write to finish before it commits.
        Thus the ordering guarantee is by *committed* cancellation, not by
        receipt of an asynchronous cancellation request.

        Do not call other store methods inside callback (same-connection nested
        transactions). The callback must be bounded by its own timeout; the
        caller must provide an isolated controller process and transport.
        This is a local SQLite fence, NOT a distributed/OS credential broker.
        """
        if minimum_seconds <= 0 or minimum_seconds > 3600:
            raise ValueError("invalid remote-write budget")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            now = int(time.time())
            row = self.db.execute(
                """SELECT lease_until FROM work
                   WHERE issue=? AND status='LEASED' AND lease_owner=?""",
                (issue, owner)).fetchone()
            if not row or row[0] <= now + minimum_seconds:
                self.db.execute("COMMIT")
                return None
            result = callback()
            self.db.execute("COMMIT")
            return result
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def snapshot(self, issue):
        row = self.db.execute(
            "SELECT issue,status,lease_owner,lease_until,attempts,retry_after,proof FROM work WHERE issue=?",
            (issue,)).fetchone()
        return dict(zip(("issue", "status", "lease_owner", "lease_until",
                         "attempts", "retry_after", "proof"), row)) if row else None


def main():
    # A GitHub Actions checkout is EPHEMERAL; never pretend its /tmp DB persists.
    path = os.environ.get("HS_DURABLE_WORKER_DB")
    if not path or not os.path.isabs(path) or path.startswith(("/tmp/", "/home/runner/")):
        raise RuntimeError("persistent absolute HS_DURABLE_WORKER_DB required")
    from continuous_dispatcher import list_open_issues, pending, valid_repo
    repo, token = os.environ["GITHUB_REPOSITORY"], os.environ["GH_TOKEN"]
    if not valid_repo(repo):
        raise ValueError("invalid repository")
    store = DurableWorkStore(path)
    try:
        all_open = list_open_issues(repo, token)
        items = pending(all_open)
        if len(items) > 1:
            raise QueueIntegrityError("duplicate open work requests")
        store.reconcile_open({i['number'] for i in all_open if isinstance(i, dict) and type(i.get('number')) is int})
        for item in items:
            store.ingest(item)
        print(json.dumps({"ingested": len(items), "agent_invoked": False,
                          "READY": False, "worker_connected": False}))
    finally:
        store.close()


if __name__ == "__main__":
    main()
