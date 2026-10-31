"""Append-only crash-replay journal for isolated AI handoffs.

Evidence only: role labels are NOT independent QA attestations. Never infer
QA_PASS, READY, or a live worker from journal entries alone.
"""
import hashlib
import json
import re
import sqlite3
from datetime import datetime

FIELDS = ("timestamp", "instruction_source", "priority", "task_id", "owner_role",
          "exact_sha", "pr", "ci_run", "qa_evidence", "state", "blocker",
          "next_action", "retry_count", "execution_id")
STATES = frozenset(("QUEUED", "CLAIMED", "CODE_COMMITTED", "CI_PASS",
                    "QA_REQUESTED", "QA_FAIL", "QA_PASS", "READY",
                    "NEXT_QUEUED", "BLOCKED", "RECOVERY_PENDING"))


class CheckpointConflict(ValueError):
    """Fail closed on inconsistent evidence."""


def _canonical(event):
    if not isinstance(event, dict) or set(event) != set(FIELDS):
        raise CheckpointConflict("exact checkpoint schema required")
    for key in ("instruction_source", "priority", "task_id", "owner_role",
                "qa_evidence", "state", "blocker", "next_action", "execution_id"):
        if not isinstance(event[key], str) or len(event[key]) > 512:
            raise CheckpointConflict("invalid field: " + key)
    if not event["instruction_source"] or not event["task_id"] or not event["execution_id"]:
        raise CheckpointConflict("source, task and execution required")
    if event["state"] not in STATES or event["owner_role"] not in ("A", "B", "C", "AUDIT"):
        raise CheckpointConflict("invalid state or role")
    if type(event["retry_count"]) is not int or event["retry_count"] < 0:
        raise CheckpointConflict("invalid retry count")
    if not (event["exact_sha"] == "MISSING" or
            isinstance(event["exact_sha"], str) and re.fullmatch(r"[0-9a-f]{40}", event["exact_sha"])):
        raise CheckpointConflict("invalid exact SHA")
    for key in ("pr", "ci_run"):
        if event[key] is not None and (type(event[key]) is not int or event[key] <= 0):
            raise CheckpointConflict("invalid " + key)
    try:
        stamp = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("timezone required")
    except (TypeError, ValueError) as exc:
        raise CheckpointConflict("invalid timestamp") from exc
    if event["state"] in ("CI_PASS", "QA_REQUESTED", "QA_PASS", "READY", "NEXT_QUEUED") and event["exact_sha"] == "MISSING":
        raise CheckpointConflict("exact SHA required")
    if event["state"] in ("QA_PASS", "READY") and not event["qa_evidence"]:
        raise CheckpointConflict("QA reference required")
    if event["state"] == "READY" and event["owner_role"] != "A":
        raise CheckpointConflict("A decision label required")
    if event["state"] == "QA_PASS" and event["owner_role"] != "B":
        raise CheckpointConflict("B QA label required")
    return json.dumps(event, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class ExecutionJournal:
    def __init__(self, path):
        if not path or path == ":memory:":
            raise ValueError("persistent SQLite file required")
        self.db = sqlite3.connect(path, timeout=15, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=15000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS execution_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, event_key TEXT NOT NULL UNIQUE,
            execution_id TEXT NOT NULL, task_id TEXT NOT NULL,
            payload TEXT NOT NULL, payload_sha256 TEXT NOT NULL)""")
        self.db.execute("""CREATE TRIGGER IF NOT EXISTS execution_events_no_update
            BEFORE UPDATE ON execution_events BEGIN SELECT RAISE(ABORT, 'append only'); END""")
        self.db.execute("""CREATE TRIGGER IF NOT EXISTS execution_events_no_delete
            BEFORE DELETE ON execution_events BEGIN SELECT RAISE(ABORT, 'append only'); END""")

    def close(self):
        self.db.close()

    def append(self, event_key, event):
        if not isinstance(event_key, str) or not re.fullmatch(r"[A-Za-z0-9:._/-]{1,160}", event_key):
            raise CheckpointConflict("invalid idempotency key")
        payload = _canonical(event)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            old = self.db.execute("SELECT payload_sha256,payload FROM execution_events WHERE event_key=?", (event_key,)).fetchone()
            if old:
                if old != (digest, payload):
                    raise CheckpointConflict("same idempotency key, different evidence")
                self.db.execute("COMMIT")
                return False
            self.db.execute("""INSERT INTO execution_events
                (event_key,execution_id,task_id,payload,payload_sha256)
                VALUES(?,?,?,?,?)""", (event_key, event["execution_id"], event["task_id"], payload, digest))
            self.db.execute("COMMIT")
            return True
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def replay(self, execution_id):
        rows = self.db.execute("""SELECT payload,payload_sha256 FROM execution_events
            WHERE execution_id=? ORDER BY id""", (execution_id,)).fetchall()
        events = []
        for payload, digest in rows:
            if hashlib.sha256(payload.encode("utf-8")).hexdigest() != digest:
                raise CheckpointConflict("journal integrity mismatch")
            event = json.loads(payload)
            _canonical(event)
            events.append(event)
        return events

    def latest(self, execution_id):
        events = self.replay(execution_id)
        return events[-1] if events else None
