"""Durable, fail-closed C rework outbox. NEVER invokes an AI agent or GitHub write.

A C/B poll may stage a rework event ONLY in the SAME SQLite transaction that
stores an independently verified immutable QA_FAIL receipt. The trusted
credential-owning host must separately authorize a Codex worker, enforce OS
isolation and a push broker, and consume these records in a future change.
No public comment, unverified verdict, or AI-generated boolean may enqueue.
"""
import re
import sqlite3
import time

SHA = re.compile(r"^[0-9a-f]{40}$")
STATE = "AWAIT_AUTHENTICATED_CODEX"


def init(db):
    db.execute("""CREATE TABLE IF NOT EXISTS cb_rework_outbox (
        request_id TEXT NOT NULL,
        product_sha TEXT NOT NULL,
        source_pr INTEGER NOT NULL,
        qa_sha TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state='AWAIT_AUTHENTICATED_CODEX'),
        created_at INTEGER NOT NULL,
        PRIMARY KEY(request_id, product_sha))""")


def stage_verified_failure(db, *, request_id, product_sha, now=None):
    """Atomically stage ONLY an existing verified QA_FAIL / C_FIXING receipt.

    Caller must already hold BEGIN IMMEDIATE and must not commit the receipt
    independently. If the transaction rolls back, both receipt and outbox
    disappear. The outbox is deliberately NOT an executable work queue.
    """
    if not isinstance(db, sqlite3.Connection) or not db.in_transaction:
        raise ValueError("BEGIN IMMEDIATE transaction required")
    if (not isinstance(request_id, str) or not request_id
            or len(request_id) > 128 or not SHA.fullmatch(str(product_sha))):
        return "INVALID"
    init(db)
    receipt = db.execute(
        """SELECT pr_number,qa_sha,qa_status,next_action
           FROM cb_qa_receipts WHERE request_id=? AND product_sha=?""",
        (request_id, product_sha)).fetchone()
    if not receipt:
        return "NOT_VERIFIED"
    source_pr, qa_sha, qa_status, next_action = receipt
    if (type(source_pr) is not int or source_pr < 1
            or not SHA.fullmatch(str(qa_sha))
            or qa_status != "QA_FAIL" or next_action != "C_FIXING"):
        return "NOT_AUTHORIZED"
    expected = (source_pr, qa_sha, STATE)
    existing = db.execute(
        """SELECT source_pr,qa_sha,state FROM cb_rework_outbox
           WHERE request_id=? AND product_sha=?""",
        (request_id, product_sha)).fetchone()
    if existing:
        return "ALREADY_STAGED" if existing == expected else "CONFLICT"
    timestamp = int(time.time() if now is None else now)
    db.execute(
        """INSERT INTO cb_rework_outbox
           (request_id,product_sha,source_pr,qa_sha,state,created_at)
           VALUES (?,?,?,?,?,?)""",
        (request_id, product_sha, source_pr, qa_sha, STATE, timestamp))
    return "STAGED"


def pending(db_path, *, request_id, product_sha):
    """Read-only handoff for future protected worker; never claims or executes."""
    if (not isinstance(request_id, str) or not request_id
            or not SHA.fullmatch(str(product_sha))):
        return None
    with sqlite3.connect(db_path, timeout=15) as db:
        init(db)
        row = db.execute(
            """SELECT source_pr,qa_sha,state,created_at FROM cb_rework_outbox
               WHERE request_id=? AND product_sha=?""",
            (request_id, product_sha)).fetchone()
    if not row:
        return None
    return dict(request_id=request_id, product_sha=product_sha,
                source_pr=row[0], qa_sha=row[1], state=row[2],
                created_at=row[3], executable=False)
