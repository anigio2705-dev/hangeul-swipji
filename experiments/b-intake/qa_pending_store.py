"""A-side QA_PENDING request ledger. Experimental local durability, not authenticated GitHub issuance."""
import json
import os
import re
import sqlite3
import stat
from pathlib import Path

SHA = re.compile(r"^[0-9a-f]{40}$")
RID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,127}$")

class PendingStore:
    def __init__(self, path):
        self.path = str(path)
        self._check_file()
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
    def _check_file(self):
        p=Path(self.path)
        if p.is_symlink():
            raise ValueError("SQLITE_SYMLINK_REJECTED")
        if p.exists():
            st=p.lstat()
            if not stat.S_ISREG(st.st_mode) or st.st_mode & 0o077:
                raise ValueError("SQLITE_UNSAFE_PERMISSIONS")
            if hasattr(self,"_identity") and self._identity!=(st.st_dev,st.st_ino):
                raise ValueError("SQLITE_FILE_REPLACED")
            self._identity=(st.st_dev,st.st_ino)
        else:
            if hasattr(self,"_identity"):
                raise ValueError("SQLITE_FILE_REPLACED")
            parent=p.parent.stat()
            if parent.st_mode & 0o022:
                raise ValueError("SQLITE_UNSAFE_DIRECTORY")
    def _db(self):
        self._check_file()
        db=sqlite3.connect(self.path,timeout=15,isolation_level=None)
        db.execute("PRAGMA busy_timeout=15000")
        if not hasattr(self,"_identity"):
            os.chmod(self.path,0o600)
            self._check_file()
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
    def consume_pending(self, request_id, task_id, product_pr, product_sha, next_state="DISPATCHED"):
        if next_state not in ("DISPATCHED","RECEIVED"):
            raise ValueError("INVALID_TRANSITION")
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            changed=db.execute("""UPDATE pending SET state=?
                WHERE request_id=? AND task_id=? AND product_pr=?
                AND product_sha=? AND state='QA_PENDING'""",
                (next_state,request_id,task_id,product_pr,product_sha)).rowcount
            db.execute("INSERT INTO request_attempts VALUES (?,?,?,?,?)",
                (request_id,task_id,product_pr,product_sha,
                 "CONSUMED_"+next_state if changed==1 else "CONSUME_REPLAY_REJECTED"))
            db.execute("COMMIT")
        if changed!=1:
            raise ValueError("UNAUTHORIZED_OR_REPLAYED_REQUEST")
        return True
    def require_pending(self, request_id, task_id, product_pr, product_sha):
        # Read-only inspection is NOT authorization; callers MUST consume atomically.
        with self._db() as db:
            row=db.execute("SELECT task_id,product_pr,product_sha,state FROM pending WHERE request_id=?",(request_id,)).fetchone()
        if row!=(task_id,product_pr,product_sha,"QA_PENDING"):
            raise ValueError("UNAUTHORIZED_OR_REPLAYED_REQUEST")
        return True
