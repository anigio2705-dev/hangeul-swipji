#!/usr/bin/env python3
"""Fail-closed recovery decision; no code execution or deployment."""
import datetime
import re
import sqlite3
SHA = re.compile(r"^[0-9a-f]{40}$")

def resume_gate(db, task_id, saved_sha, current_sha=None, qa_sha=None,
                qa_authenticated=False, lease_valid=False, actor_authorized=False,
                sources_verified=False, conflict=False):
    if not isinstance(saved_sha, str) or not SHA.fullmatch(saved_sha):
        state, reason = "RECOVERY_BLOCKED", "INVALID_SAVED_SHA"
    elif conflict or (current_sha is not None and
                      (not isinstance(current_sha, str) or not SHA.fullmatch(current_sha))):
        state, reason = "RECOVERY_BLOCKED", "CONFLICT_OR_INVALID_CURRENT_SHA"
    elif current_sha is not None and current_sha != saved_sha:
        state, reason = "RECOVERY_BLOCKED", "PRODUCT_SHA_CHANGED_QA_NOT_TRANSFERABLE"
    elif qa_sha is not None and qa_sha != saved_sha:
        state, reason = "RECOVERY_BLOCKED", "QA_SHA_MISMATCH"
    elif all((current_sha == saved_sha, qa_sha == saved_sha, qa_authenticated,
              lease_valid, actor_authorized, sources_verified)):
        state, reason = "VERIFIED_READY_TO_RESUME", "ALL_EXTERNAL_GATES_VERIFIED"
    else:
        state, reason = "RECOVERED_UNVERIFIED", "MISSING_CURRENT_EXTERNAL_VERIFICATION"
    with sqlite3.connect(db) as cx:
        cx.execute("CREATE TABLE IF NOT EXISTS resume_decisions (task_id TEXT PRIMARY KEY, saved_sha TEXT NOT NULL, current_sha TEXT, qa_sha TEXT, state TEXT NOT NULL, reason TEXT NOT NULL, checked_at TEXT NOT NULL)")
        cx.execute("INSERT INTO resume_decisions VALUES (?,?,?,?,?,?,?) ON CONFLICT(task_id) DO UPDATE SET saved_sha=excluded.saved_sha,current_sha=excluded.current_sha,qa_sha=excluded.qa_sha,state=excluded.state,reason=excluded.reason,checked_at=excluded.checked_at",
                   (str(task_id),saved_sha,current_sha,qa_sha,state,reason,datetime.datetime.now(datetime.timezone.utc).isoformat()))
    return {"task_id":str(task_id),"state":state,"reason":reason,
            "execution_allowed":state == "VERIFIED_READY_TO_RESUME"}
