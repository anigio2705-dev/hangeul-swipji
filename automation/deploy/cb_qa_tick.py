"""Fail-closed, restart-safe C/B QA polling tick. NO AI execution or READY grants.

Run at most once per scheduled tick on a persistent host volume. All input
identities/SHA values must come from protected controller configuration, never
from an issue comment or a model-edited PR. This module only performs GitHub
GETs and writes local SQLite; it never posts, pushes, or changes A READY.
"""
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path

from cb_qa_evidence import SHA, collect_github_evidence
from cb_qa_verdict_store import accept_verdict, init as init_receipts

LEASE_SECONDS = 180
POLL_SECONDS = 240
TERMINAL = {"QA_PASS_VERIFIED", "C_REWORK_REQUIRED", "BLOCKED_245", "CONFLICT"}


def _init(db):
    db.execute("""CREATE TABLE IF NOT EXISTS cb_qa_ticks (
        request_id TEXT NOT NULL, product_sha TEXT NOT NULL,
        source_pr INTEGER NOT NULL, qa_pr INTEGER NOT NULL,
        qa_sha TEXT NOT NULL, run_id INTEGER NOT NULL,
        state TEXT NOT NULL, lease_owner TEXT, lease_until INTEGER NOT NULL,
        next_check INTEGER NOT NULL, updated_at INTEGER NOT NULL,
        detail TEXT NOT NULL,
        PRIMARY KEY(request_id, product_sha))""")


def _safe_reason(value):
    # No API exception bodies, tokens or GitHub payloads in persistent logs.
    return str(value)[:160] if value in (
        "missing independent B evidence", "independent B verdict verified",
        "conflicting immutable receipt", "QA_FAIL requires C rework",
        "QA_PASS awaits A decision", "retry limit reached",
        "read-only GitHub fetch failed") else "independent B evidence unavailable"


def _result(state, detail, next_check=None):
    return {"state": state, "detail": detail, "next_check": next_check}


def run_tick(db_path, *, request_id, source_pr_number, qa_pr_number,
             run_id, product_sha, qa_sha, trusted_b_login, token,
             now=None, get_json=None):
    """One read-only evidence poll with durable lease and exact-SHA receipt.

    Unverified evidence is WAITING, not QA_FAIL. A verified QA_FAIL records a
    rework requirement, but DOES NOT start Codex or claim a queued AI worker.
    An expired read-only lease may be reclaimed; immutable receipts prevent
    duplicate verdict changes. No external POST or push is performed.
    """
    now = int(time.time()) if now is None else int(now)
    if (not request_id or len(request_id) > 128
            or any(type(n) is not int or n < 1
                   for n in (source_pr_number, qa_pr_number, run_id))
            or not SHA.fullmatch(str(product_sha))
            or not SHA.fullmatch(str(qa_sha)) or product_sha == qa_sha):
        return _result("BLOCKED_CONFIG", "invalid pinned request or SHA")
    if not trusted_b_login or not token:
        return _result("BLOCKED_CONFIG", "protected B identity/token missing")
    owner = uuid.uuid4().hex
    with sqlite3.connect(db_path, timeout=15) as db:
        db.execute("BEGIN IMMEDIATE")
        _init(db)
        row = db.execute(
            """SELECT source_pr,qa_pr,qa_sha,run_id,state,lease_until,
                      next_check,detail FROM cb_qa_ticks
               WHERE request_id=? AND product_sha=?""",
            (request_id, product_sha)).fetchone()
        if row:
            src, qa, stored_sha, run, state, lease_until, next_check, detail = row
            if (src, qa, stored_sha, run) != (
                    source_pr_number, qa_pr_number, qa_sha, run_id):
                return _result("BLOCKED_CONFIG", "pinned QA identity changed")
            if state in TERMINAL:
                return _result(state, detail)
            if lease_until > now:
                return _result("RUNNING", "read-only evidence poll leased", lease_until)
            if next_check > now:
                return _result("WAITING", detail, next_check)
        else:
            db.execute(
                """INSERT INTO cb_qa_ticks VALUES
                   (?,?,?,?,?,?,'WAITING',NULL,0,0,?,'first poll')""",
                (request_id, product_sha, source_pr_number, qa_pr_number,
                 qa_sha, run_id, now))
        db.execute(
            """UPDATE cb_qa_ticks SET state='RUNNING',lease_owner=?,
               lease_until=?,updated_at=?,detail='read-only evidence poll'
               WHERE request_id=? AND product_sha=?""",
            (owner, now + LEASE_SECONDS, now, request_id, product_sha))

    try:
        evidence = collect_github_evidence(
            token=token, source_pr_number=source_pr_number,
            qa_pr_number=qa_pr_number, run_id=run_id,
            source_sha=product_sha, qa_sha=qa_sha,
            trusted_b_login=trusted_b_login, get_json=get_json)
    except Exception:
        # Deliberately never persist exception strings: they may leak auth.
        evidence = {"status": "UNVERIFIED", "reason": "read-only GitHub fetch failed"}

    # IMPORTANT: do not write a receipt before validating fencing.
    # A slow GitHub GET may outlive LEASE_SECONDS; another tick can then
    # acquire the lease. Receipt + state must commit in ONE transaction.
    with sqlite3.connect(db_path, timeout=15) as db:
        db.execute("BEGIN IMMEDIATE")
        _init(db)
        row = db.execute(
            "SELECT lease_owner FROM cb_qa_ticks WHERE request_id=? AND product_sha=?",
            (request_id, product_sha)).fetchone()
        if not row or row[0] != owner:
            return _result("STALE_LEASE", "newer read-only poll owns state")

        verdict = evidence.get("status")
        if verdict in ("QA_PASS", "QA_FAIL"):
            proof = json.dumps({
                "source_pr": source_pr_number, "qa_pr": qa_pr_number,
                "run_id": run_id, "product_sha": product_sha, "qa_sha": qa_sha,
                "reviewer": trusted_b_login, "verified_status": verdict
            }, sort_keys=True)
            init_receipts(db)
            existing = db.execute(
                """SELECT qa_sha,qa_status,evidence,next_action
                   FROM cb_qa_receipts WHERE request_id=? AND product_sha=?""",
                (request_id, product_sha)).fetchone()
            if existing:
                receipt = ("CONFLICT" if existing[:3] !=
                           (qa_sha, verdict, proof) else existing[3])
            else:
                failures = db.execute(
                    """SELECT COUNT(*) FROM cb_qa_receipts
                       WHERE request_id=? AND qa_status='QA_FAIL'
                         AND product_sha<>?""",
                    (request_id, product_sha)).fetchone()[0]
                receipt = accept_verdict(
                    db_path, request_id=request_id, pr_number=source_pr_number,
                    product_sha=product_sha, qa_sha=qa_sha, verdict=verdict,
                    evidence=proof, verified_by_b=True, ci_success=True,
                    retry_count=failures, now=now, db=db)
            if receipt == "AWAIT_A_REVIEW":
                state, detail = "QA_PASS_VERIFIED", "QA_PASS awaits A decision"
            elif receipt == "C_FIXING":
                state, detail = "C_REWORK_REQUIRED", "QA_FAIL requires C rework"
            elif receipt == "BLOCKER_245":
                state, detail = "BLOCKED_245", "retry limit reached"
            else:
                state, detail = "CONFLICT", "conflicting immutable receipt"
        else:
            state = "WAITING_B_EVIDENCE"
            detail = _safe_reason(evidence.get("reason"))

        next_check = 0 if state in TERMINAL else now + POLL_SECONDS
        db.execute(
            """UPDATE cb_qa_ticks SET state=?,lease_owner=NULL,
               lease_until=0,next_check=?,updated_at=?,detail=?
               WHERE request_id=? AND product_sha=?""",
            (state, next_check, now, detail, request_id, product_sha))
    return _result(state, detail, next_check or None)


def main():
    """Protected environment + systemd LoadCredential; never print secrets."""
    env = os.environ
    token_file = env.get("CB_GH_TOKEN_FILE", "")
    try:
        token = Path(token_file).read_text().strip() if token_file else ""
    except OSError:
        token = ""
    def number(key):
        try:
            return int(env.get(key, "0"))
        except ValueError:
            return 0
    result = run_tick(
        env.get("CB_DB_PATH", "/var/lib/hangeul-swipji/cb-qa.sqlite3"),
        request_id=env.get("CB_REQUEST_ID", ""),
        source_pr_number=number("CB_SOURCE_PR"),
        qa_pr_number=number("CB_QA_PR"),
        run_id=number("CB_QA_RUN_ID"),
        product_sha=env.get("CB_PRODUCT_SHA", ""),
        qa_sha=env.get("CB_QA_SHA", ""),
        trusted_b_login=env.get("CB_TRUSTED_B_LOGIN", ""),
        token=token)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["state"] not in ("BLOCKED_CONFIG", "CONFLICT") else 2


if __name__ == "__main__":
    raise SystemExit(main())
