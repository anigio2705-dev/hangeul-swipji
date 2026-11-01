#!/usr/bin/env python3
"""Isolated fail-closed restart experiment. NEVER an execution authorization."""
import datetime
import re
import sqlite3

SHA = re.compile(r"^[0-9a-f]{40}$")


def _valid_sha(value):
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def resume_gate(db, task_id, saved_sha, current_sha=None, qa_sha=None,
                qa_authenticated=False, lease_valid=False, actor_authorized=False,
                sources_verified=False, conflict=False, expected_revision=None):
    """Record a recovery observation with revision fencing.

    Caller booleans are untrusted and NEVER grant permission to run an AI worker.
    A blocking observation may safely supersede older state; a blocked record is
    sticky. Every non-blocking update requires the latest revision (CAS).
    """
    if not _valid_sha(saved_sha):
        state, reason = "RECOVERY_BLOCKED", "INVALID_SAVED_SHA"
    elif conflict or (current_sha is not None and not _valid_sha(current_sha)):
        state, reason = "RECOVERY_BLOCKED", "CONFLICT_OR_INVALID_CURRENT_SHA"
    elif current_sha is not None and current_sha != saved_sha:
        state, reason = "RECOVERY_BLOCKED", "PRODUCT_SHA_CHANGED_QA_NOT_TRANSFERABLE"
    elif qa_sha is not None and qa_sha != saved_sha:
        state, reason = "RECOVERY_BLOCKED", "QA_SHA_MISMATCH"
    elif all((current_sha == saved_sha, qa_sha == saved_sha, qa_authenticated,
              lease_valid, actor_authorized, sources_verified)):
        # Informational only: these flags come from the caller, not GitHub/Actions.
        state, reason = "VERIFIED_READY_TO_RESUME", "CALLER_FLAGS_ONLY_NOT_AUTHORIZED"
    else:
        state, reason = "RECOVERED_UNVERIFIED", "MISSING_CURRENT_EXTERNAL_VERIFICATION"

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with sqlite3.connect(db, timeout=10, isolation_level=None) as cx:
        cx.execute("BEGIN IMMEDIATE")
        cx.execute("""CREATE TABLE IF NOT EXISTS resume_decisions (
            task_id TEXT PRIMARY KEY, saved_sha TEXT NOT NULL, current_sha TEXT,
            qa_sha TEXT, state TEXT NOT NULL, reason TEXT NOT NULL,
            checked_at TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1)""")
        columns = {row[1] for row in cx.execute("PRAGMA table_info(resume_decisions)")}
        if "revision" not in columns:
            cx.execute("ALTER TABLE resume_decisions ADD COLUMN revision INTEGER NOT NULL DEFAULT 1")
        key = str(task_id)
        row = cx.execute("SELECT state,reason,revision FROM resume_decisions WHERE task_id=?", (key,)).fetchone()
        if row is None:
            cx.execute("INSERT INTO resume_decisions VALUES (?,?,?,?,?,?,?,1)",
                       (key, saved_sha, current_sha, qa_sha, state, reason, now))
            revision = 1
        else:
            old_state, old_reason, revision = row
            if old_state == "RECOVERY_BLOCKED" and state != "RECOVERY_BLOCKED":
                state, reason = old_state, "BLOCKED_REQUIRES_NEW_TRUSTED_ATTESTATION"
            elif expected_revision is not None and expected_revision != revision:
                state, reason = old_state, "STALE_REVISION"
            elif expected_revision is None and state != "RECOVERY_BLOCKED":
                state, reason = old_state, "REVISION_REQUIRED"
            else:
                changed = cx.execute("""UPDATE resume_decisions
                    SET saved_sha=?,current_sha=?,qa_sha=?,state=?,reason=?,checked_at=?,revision=revision+1
                    WHERE task_id=? AND revision=?""",
                    (saved_sha, current_sha, qa_sha, state, reason, now, key, revision))
                if changed.rowcount != 1:
                    raise RuntimeError("RECOVERY_REVISION_RACE")
                revision += 1
        cx.commit()
    return {"task_id": str(task_id), "state": state, "reason": reason,
            "revision": revision, "execution_allowed": False}
