"""Durable fail-closed A/B handoff ledger. External GitHub dispatch is not implemented."""
import json
import sqlite3
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS handoffs(
 request_id TEXT PRIMARY KEY, task_id INTEGER NOT NULL, product_pr INTEGER NOT NULL,
 product_sha TEXT NOT NULL, base_sha TEXT NOT NULL, ci_run_url TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('QA_PENDING','QA_RECEIVED','QA_HANDOFF_TIMEOUT','QA_PASS','QA_FAIL')),
 attempts INTEGER NOT NULL DEFAULT 0, last_attempt TEXT, created_at TEXT NOT NULL,
 received_at TEXT, qa_sha TEXT, qa_ci_url TEXT, failure_repro TEXT, next_action TEXT,
 UNIQUE(task_id,product_sha));
CREATE TABLE IF NOT EXISTS handoff_audit(
 id INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT NOT NULL,
 event TEXT NOT NULL, details TEXT NOT NULL, recorded_at TEXT NOT NULL);
"""
def utcnow():
    return datetime.now(timezone.utc).isoformat()
def connect(path):
    db=sqlite3.connect(path,isolation_level=None)
    db.execute("PRAGMA busy_timeout=5000")
    db.executescript(SCHEMA)
    return db
def audit(db,request_id,event,details):
    db.execute("INSERT INTO handoff_audit(request_id,event,details,recorded_at) VALUES(?,?,?,?)",
               (request_id,event,json.dumps(details,sort_keys=True),utcnow()))
def enqueue(db,request_id,task_id,product_pr,product_sha,base_sha,ci_run_url,now=None):
    now=now or utcnow()
    fields=(task_id,product_pr,product_sha,base_sha,ci_run_url)
    with db:
        old=db.execute("SELECT task_id,product_pr,product_sha,base_sha,ci_run_url FROM handoffs WHERE request_id=?",(request_id,)).fetchone()
        if old:
            if old != fields:
                audit(db,request_id,"HANDOFF_CONFLICT",{"existing":old,"incoming":fields})
                raise ValueError("request_id reused with different product/PR/SHA")
        else:
            db.execute("INSERT INTO handoffs(request_id,task_id,product_pr,product_sha,base_sha,ci_run_url,state,created_at) VALUES(?,?,?,?,?,?,'QA_PENDING',?)",
                       (request_id,*fields,now))
            audit(db,request_id,"QA_PENDING",{"product_sha":product_sha})
    return db.execute("SELECT state FROM handoffs WHERE request_id=?",(request_id,)).fetchone()[0]
def claim_for_dispatch(db,request_id,max_attempts=3,now=None):
    now=now or utcnow()
    with db:
        cur=db.execute("UPDATE handoffs SET attempts=attempts+1,last_attempt=? WHERE request_id=? AND state IN ('QA_PENDING','QA_HANDOFF_TIMEOUT') AND attempts<?",
                       (now,request_id,max_attempts))
        if cur.rowcount: audit(db,request_id,"DISPATCH_ATTEMPT",{"at":now})
    return cur.rowcount==1
def mark_timeout(db,request_id):
    with db:
        cur=db.execute("UPDATE handoffs SET state='QA_HANDOFF_TIMEOUT' WHERE request_id=? AND state='QA_PENDING'",(request_id,))
        if cur.rowcount: audit(db,request_id,"QA_HANDOFF_TIMEOUT",{})
    return cur.rowcount==1
def _trusted_evidence(evidence,sha):
    # A local string or GitHub comment is never proof. Caller must supply an independently
    # authenticated GitHub Actions verifier result; this gate deliberately fails closed.
    return bool(evidence and evidence.get("verified_by_trusted_actions_api") is True
                and evidence.get("product_sha")==sha
                and evidence.get("workflow_run_id") and evidence.get("job_id")
                and evidence.get("conclusion")=="success"
                and evidence.get("trusted_identity_verified") is True)
def record_received(db,request_id,product_sha,now=None,evidence=None):
    if not _trusted_evidence(evidence,product_sha):
        with db: audit(db,request_id,"UNTRUSTED_QA_RECEIPT",{"product_sha":product_sha})
        return False
    now=now or utcnow()
    with db:
        cur=db.execute("UPDATE handoffs SET state='QA_RECEIVED',received_at=? WHERE request_id=? AND product_sha=? AND state IN ('QA_PENDING','QA_HANDOFF_TIMEOUT')",(now,request_id,product_sha))
        if cur.rowcount: audit(db,request_id,"QA_RECEIVED",{"run":evidence["workflow_run_id"]})
    return cur.rowcount==1
def record_verdict(db,request_id,product_sha,qa_sha,qa_status,ci_run_url,failure_repro,next_action,evidence=None):
    if qa_status not in ("QA_PASS","QA_FAIL") or not _trusted_evidence(evidence,product_sha):
        with db: audit(db,request_id,"UNTRUSTED_QA_VERDICT",{"status":qa_status})
        return False
    with db:
        cur=db.execute("""UPDATE handoffs SET state=?,qa_sha=?,qa_ci_url=?,failure_repro=?,next_action=?
           WHERE request_id=? AND product_sha=? AND state='QA_RECEIVED'""",
           (qa_status,qa_sha,ci_run_url,failure_repro,next_action,request_id,product_sha))
        if cur.rowcount: audit(db,request_id,qa_status,{"qa_sha":qa_sha,"run":evidence["workflow_run_id"]})
    return cur.rowcount==1
