"""C-side durable B QA verdict ingestion. A GitHub comment is not proof of QA.

Only a trusted controller may call accept_verdict after independently verifying
B-only PR, exact product base SHA and successful independent Actions run.
This module never fabricates QA_PASS or triggers a push/deployment.
"""
import re
import sqlite3
import time

FIELDS = ("REQUEST_ID", "TASK_ID", "SOURCE_ROLE", "TARGET_ROLE",
          "PR_NUMBER", "PRODUCT_SHA", "QA_SHA", "CI_RUN_URL", "QA_STATUS",
          "FAILURE_EVIDENCE", "RETRY_COUNT", "NEXT_ACTION", "UPDATED_AT")
SHA = re.compile(r"^[0-9a-f]{40}$")
STATES = {"QA_REQUESTED", "QA_RUNNING", "QA_PASS", "QA_FAIL",
          "FIX_REQUESTED", "C_FIXING", "NEW_SHA"}
MAX_FIXES = 3


def init(db):
    db.execute("""CREATE TABLE IF NOT EXISTS cb_qa_receipts (
        request_id TEXT NOT NULL, product_sha TEXT NOT NULL,
        pr_number INTEGER NOT NULL, qa_sha TEXT NOT NULL,
        qa_status TEXT NOT NULL, evidence TEXT NOT NULL,
        retry_count INTEGER NOT NULL DEFAULT 0,
        next_action TEXT NOT NULL, updated_at INTEGER NOT NULL,
        PRIMARY KEY(request_id, product_sha))""")


def accept_verdict(db_path, *, request_id, pr_number, product_sha,
                   qa_sha, verdict, evidence, verified_by_b,
                   ci_success, retry_count=0, now=None):
    """Store only independently verified B verdicts; new SHA is a new key.

    verified_by_b must come from an external trusted verifier checking the
    B-owned QA PR's base SHA, author, workflow and exact CI run. Never derive
    it from a public comment or a C-generated field.
    """
    if (not request_id or len(request_id) > 128
            or type(pr_number) is not int or pr_number < 1
            or not SHA.fullmatch(product_sha)
            or not SHA.fullmatch(qa_sha)
            or verdict not in ("QA_PASS", "QA_FAIL")
            or verified_by_b is not True or ci_success is not True
            or not evidence or type(retry_count) is not int or retry_count < 0):
        return "UNVERIFIED"
    action = ("AWAIT_A_REVIEW" if verdict == "QA_PASS" else
              "C_FIXING" if retry_count < MAX_FIXES else "BLOCKER_245")
    with sqlite3.connect(db_path, timeout=15) as db:
        db.execute("BEGIN IMMEDIATE")
        init(db)
        old = db.execute(
            "SELECT pr_number,qa_sha,qa_status,evidence,retry_count,next_action "
            "FROM cb_qa_receipts WHERE request_id=? AND product_sha=?",
            (request_id, product_sha)).fetchone()
        desired = (pr_number, qa_sha, verdict, evidence, retry_count, action)
        if old:
            # Immutable receipt: a different result for the same product SHA
            # cannot silently replace an independent QA decision.
            return "DUPLICATE" if old == desired else "CONFLICT"
        db.execute("""INSERT INTO cb_qa_receipts
            (request_id,product_sha,pr_number,qa_sha,qa_status,evidence,
             retry_count,next_action,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (request_id, product_sha, *desired[:5], action,
             int(time.time() if now is None else now)))
    return action


def pending_fix(db_path, request_id, product_sha):
    with sqlite3.connect(db_path) as db:
        init(db)
        row = db.execute(
            "SELECT qa_status,evidence,retry_count,next_action FROM cb_qa_receipts "
            "WHERE request_id=? AND product_sha=?",
            (request_id, product_sha)).fetchone()
    if not row or row[0] != "QA_FAIL":
        return None
    return {"FAILURE_EVIDENCE": row[1], "RETRY_COUNT": row[2],
            "NEXT_ACTION": row[3], "PRODUCT_SHA": product_sha}
