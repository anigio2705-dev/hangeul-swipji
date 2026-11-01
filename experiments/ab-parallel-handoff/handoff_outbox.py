"""Durable A-to-B handoff outbox. No AI execution or QA authorization."""
import sqlite3
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS handoffs (
 request_id TEXT PRIMARY KEY,
 task_id INTEGER NOT NULL,
 product_pr INTEGER NOT NULL,
 product_sha TEXT NOT NULL,
 base_sha TEXT NOT NULL,
 ci_run_url TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('QA_PENDING','QA_RECEIVED','QA_HANDOFF_TIMEOUT')),
 attempts INTEGER NOT NULL DEFAULT 0,
 last_attempt TEXT,
 created_at TEXT NOT NULL,
 received_at TEXT,
 UNIQUE(task_id, product_sha)
);
"""

def connect(path):
    db = sqlite3.connect(path, isolation_level=None)
    db.execute("PRAGMA busy_timeout=5000")
    db.executescript(SCHEMA)
    return db

def enqueue(db, request_id, task_id, product_pr, product_sha, base_sha, ci_run_url, now=None):
    now = now or datetime.now(timezone.utc).isoformat()
    with db:
        db.execute("INSERT OR IGNORE INTO handoffs(request_id,task_id,product_pr,product_sha,base_sha,ci_run_url,state,created_at) VALUES(?,?,?,?,?,?,'QA_PENDING',?)",
                   (request_id,task_id,product_pr,product_sha,base_sha,ci_run_url,now))
    return db.execute("SELECT * FROM handoffs WHERE request_id=?", (request_id,)).fetchone()

def claim_for_dispatch(db, request_id, max_attempts=3, now=None):
    now = now or datetime.now(timezone.utc).isoformat()
    with db:
        cursor = db.execute("""UPDATE handoffs SET attempts=attempts+1,last_attempt=?
            WHERE request_id=? AND state IN ('QA_PENDING','QA_HANDOFF_TIMEOUT') AND attempts<?""",
            (now,request_id,max_attempts))
    return cursor.rowcount == 1

def mark_timeout(db, request_id):
    with db:
        cursor=db.execute("UPDATE handoffs SET state='QA_HANDOFF_TIMEOUT' WHERE request_id=? AND state='QA_PENDING'",(request_id,))
    return cursor.rowcount == 1

def record_received(db, request_id, product_sha, now=None):
    now=now or datetime.now(timezone.utc).isoformat()
    with db:
        cursor=db.execute("""UPDATE handoffs SET state='QA_RECEIVED',received_at=?
            WHERE request_id=? AND product_sha=? AND state IN ('QA_PENDING','QA_HANDOFF_TIMEOUT')""",
            (now,request_id,product_sha))
    return cursor.rowcount == 1
