"""A-side QA_PENDING request ledger. Experimental local durability, not authenticated GitHub issuance."""
import json
import os
import re
import sqlite3
from pathlib import Path

SHA = re.compile(r"^[0-9a-f]{40}$")
RID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,127}$")

class PendingStore:
    def __init__(self, path):
        self.path = str(path)
        with self._db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS pending (
                request_id TEXT PRIMARY KEY, task_id INTEGER NOT NULL,
                product_pr INTEGER NOT NULL, product_sha TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('QA_PENDING','DISPATCHED','RECEIVED')),
                UNIQUE(task_id, product_pr, product_sha)
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS request_attempts (
                request_id TEXT NOT NULL, task_id INTEGER NOT NULL,
                product_pr INTEGER NOT NULL, product_sha TEXT NOT NULL,
                result TEXT NOT NULL
            )""")
    def _db(self):
        db=sqlite3.connect(self.path,timeout=15,isolation_level=None)
        db.execute("PRAGMA busy_timeout=15000")
        return db
    def issue(self, request_id, task_id, product_pr, product_sha):
        if not RID.fullmatch(request_id) or not isinstance(task_id,int) or not 1<=task_id<=160 or not isinstance(product_pr,int) or product_pr<1 or not SHA.fullmatch(product_sha):
            raise ValueError("INVALID_QA_PENDING")
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            existing=db.execute("SELECT task_id,product_pr,product_sha FROM pending WHERE request_id=?",(request_id,)).fetchone()
            if existing:
                db.execute("INSERT INTO request_attempts VALUES (?,?,?,?,?)",(request_id,task_id,product_pr,product_sha,"REPLAY_REJECTED"))
                db.execute("COMMIT")
                raise ValueError("REQUEST_ID_REPLAY")
            if db.execute("SELECT 1 FROM pending WHERE task_id=? AND product_pr=? AND product_sha=?",(task_id,product_pr,product_sha)).fetchone():
                db.execute("INSERT INTO request_attempts VALUES (?,?,?,?,?)",(request_id,task_id,product_pr,product_sha,"DUPLICATE_PRODUCT_REJECTED"))
                db.execute("COMMIT")
                raise ValueError("DUPLICATE_PRODUCT_REQUEST")
            db.execute("INSERT INTO pending VALUES (?,?,?,?,?)",(request_id,task_id,product_pr,product_sha,"QA_PENDING"))
            db.execute("INSERT INTO request_attempts VALUES (?,?,?,?,?)",(request_id,task_id,product_pr,product_sha,"ISSUED"))
            db.execute("COMMIT")
    def require_pending(self, request_id, task_id, product_pr, product_sha):
        with self._db() as db:
            row=db.execute("SELECT task_id,product_pr,product_sha,state FROM pending WHERE request_id=?",(request_id,)).fetchone()
        if row!=(task_id,product_pr,product_sha,"QA_PENDING"):
            raise ValueError("UNAUTHORIZED_OR_REPLAYED_REQUEST")
        return True
