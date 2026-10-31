"""Broker-owned durable push authority. No network transport is enabled here.

The database MUST live under the dedicated broker OS account and must never be
writable by the coding agent. A reserved push is not permission to bypass the
separate OS/cgroup transport gate. SIGKILL during an in-flight push always
requires reconciliation; never infer success from SQLite alone.
"""
import re
import secrets
import sqlite3
import time

SHA = re.compile(r"[0-9a-f]{40}\\Z")
BRANCH = re.compile(r"(?:work|automation|agent)/[A-Za-z0-9][A-Za-z0-9._/-]{0,100}\\Z")


class BrokerDenied(RuntimeError):
    """No remote write is authorized."""


class BrokerAuthority:
    def __init__(self, path, *, clock=time.time):
        if not path or path == ":memory:":
            raise ValueError("durable broker-owned database required")
        self.clock = clock
        self.db = sqlite3.connect(path, timeout=15, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=15000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS broker_push_lease (
            task TEXT PRIMARY KEY, token TEXT NOT NULL, sha TEXT NOT NULL,
            branch TEXT NOT NULL, expires REAL NOT NULL,
            state TEXT NOT NULL CHECK(state IN
                ('ACTIVE','PUSH_IN_FLIGHT','REVOKED','PUSH_UNCERTAIN','VERIFIED')),
            updated REAL NOT NULL)""")

    def close(self):
        self.db.close()

    def _transaction(self, fn):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            result = fn()
            self.db.execute("COMMIT")
            return result
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def issue(self, task, sha, branch, *, ttl=60):
        if (not isinstance(task, str) or not re.fullmatch(r"[A-Za-z0-9:._/-]{1,120}", task)
                or not isinstance(sha, str) or not SHA.fullmatch(sha)
                or not isinstance(branch, str) or not BRANCH.fullmatch(branch)
                or ".." in branch or "//" in branch or branch.endswith(("/", "."))
                or not 1 <= ttl <= 300):
            raise BrokerDenied("invalid task, exact SHA, isolated branch or TTL")
        now = self.clock()
        token = secrets.token_hex(32)

        def write():
            old = self.db.execute("SELECT state FROM broker_push_lease WHERE task=?",
                                  (task,)).fetchone()
            if old:
                raise BrokerDenied("task already exists; never reuse or reset a fence")
            self.db.execute("""INSERT INTO broker_push_lease
                (task,token,sha,branch,expires,state,updated)
                VALUES(?,?,?,?,?,'ACTIVE',?)""",
                (task, token, sha, branch, now + ttl, now))
            return token
        return self._transaction(write)

    def reserve(self, task, token, sha, branch):
        """One-shot reservation; caller still needs OS isolation and a fresh fence."""
        now = self.clock()

        def write():
            row = self.db.execute("""SELECT token,sha,branch,expires,state
                FROM broker_push_lease WHERE task=?""", (task,)).fetchone()
            if (not row or row != (token, sha, branch, row[3], "ACTIVE")
                    or row[3] <= now):
                raise BrokerDenied("stale, expired, mismatched or consumed lease")
            self.db.execute("""UPDATE broker_push_lease SET state='PUSH_IN_FLIGHT',
                updated=? WHERE task=?""", (now, task))
            return True
        return self._transaction(write)

    def live(self, task, token, sha, branch):
        """Read-only status check; never use this alone to authorize a push."""
        row = self.db.execute("""SELECT token,sha,branch,expires,state
            FROM broker_push_lease WHERE task=?""", (task,)).fetchone()
        return bool(row and row == (token, sha, branch, row[3], "PUSH_IN_FLIGHT")
                    and row[3] > self.clock())

    def revoke(self, task):
        """A committed cancellation cannot be silently reactivated."""
        now = self.clock()

        def write():
            row = self.db.execute("SELECT state FROM broker_push_lease WHERE task=?",
                                  (task,)).fetchone()
            if not row:
                raise BrokerDenied("unknown task")
            state = row[0]
            if state == "PUSH_IN_FLIGHT":
                target = "PUSH_UNCERTAIN"
            elif state == "ACTIVE":
                target = "REVOKED"
            else:
                return state
            self.db.execute("UPDATE broker_push_lease SET state=?,updated=? WHERE task=?",
                            (target, now, task))
            return target
        return self._transaction(write)

    def mark_verified(self, task, token, sha, branch, remote_sha):
        """Requires caller's independent remote SHA proof, never trust agent output."""
        if remote_sha != sha:
            raise BrokerDenied("remote SHA mismatch")
        now = self.clock()

        def write():
            row = self.db.execute("""SELECT token,sha,branch,expires,state
                FROM broker_push_lease WHERE task=?""", (task,)).fetchone()
            if (not row or row != (token, sha, branch, row[3], "PUSH_IN_FLIGHT")
                    or row[3] <= now):
                raise BrokerDenied("revoked, expired or mismatched completion")
            self.db.execute("""UPDATE broker_push_lease SET state='VERIFIED',
                updated=? WHERE task=?""", (now, task))
            return True
        return self._transaction(write)

    def recover(self):
        """After restart quarantine every possibly spawned transport."""
        now = self.clock()

        def write():
            in_flight = self.db.execute("""UPDATE broker_push_lease
                SET state='PUSH_UNCERTAIN',updated=?
                WHERE state='PUSH_IN_FLIGHT'""", (now,)).rowcount
            expired = self.db.execute("""UPDATE broker_push_lease
                SET state='REVOKED',updated=?
                WHERE state='ACTIVE' AND expires<=?""", (now, now)).rowcount
            return {"uncertain": in_flight, "expired": expired}
        return self._transaction(write)

    def state(self, task):
        row = self.db.execute("SELECT state FROM broker_push_lease WHERE task=?",
                              (task,)).fetchone()
        return row[0] if row else None
