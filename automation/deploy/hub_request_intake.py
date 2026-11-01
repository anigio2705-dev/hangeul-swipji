"""Read-only GitHub #245 -> durable C coordination inbox.

Issue comments are UNTRUSTED DATA: never B QA, A READY or permission
to execute Codex. No POST, push, deployment, secrets or AI API calls.
"""
import json
import os
import re
import sqlite3
import time
import urllib.request
from pathlib import Path

ISSUE = 245
API = "https://api.github.com/repos/anigio2705-dev/hangeul-swipji/issues/245/comments"
SHA = re.compile(r"^[0-9a-f]{40}$")
REQUEST_ID = re.compile(r"^HUB-[0-9]{8}-[A-D]-[A-Za-z0-9-]{1,64}$")
KEY_VALUE = re.compile(r"^(REQUEST_ID|FROM|TO|TYPE|PR_NUMBER|PRODUCT_SHA)\s*[:=]\s*(\S+)\s*$")
KINDS = {"HELP", "BLOCKER", "QA", "D_REVIEW_REQUEST", "RESEARCH"}


def init(db):
    db.execute("""CREATE TABLE IF NOT EXISTS hub_cursor (
        issue INTEGER PRIMARY KEY, last_comment_id INTEGER NOT NULL,
        updated_at INTEGER NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS hub_requests (
        request_id TEXT PRIMARY KEY, comment_id INTEGER NOT NULL UNIQUE,
        author TEXT NOT NULL, from_role TEXT NOT NULL, to_role TEXT NOT NULL,
        kind TEXT NOT NULL, pr_number INTEGER NOT NULL, product_sha TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state='UNTRUSTED_INTAKE'),
        created_at INTEGER NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS hub_intake_audit (
        comment_id INTEGER PRIMARY KEY, disposition TEXT NOT NULL,
        recorded_at INTEGER NOT NULL)""")


def parse_request(comment):
    """Parse metadata only; never persist arbitrary issue-comment content."""
    if not isinstance(comment, dict) or not isinstance(comment.get("body"), str):
        return None
    fields = {}
    for part in re.split(r"[\n;]", comment["body"]):
        match = KEY_VALUE.fullmatch(part.strip())
        if match:
            if match[1] in fields:
                return None
            fields[match[1]] = match[2].strip(chr(96))
    if set(fields) != {"REQUEST_ID", "FROM", "TO", "TYPE", "PR_NUMBER", "PRODUCT_SHA"}:
        return None
    if (not REQUEST_ID.fullmatch(fields["REQUEST_ID"])
            or fields["FROM"] not in "ABCD" or len(fields["FROM"]) != 1
            or fields["TO"] not in "ABCD" or len(fields["TO"]) != 1
            or fields["TYPE"] not in KINDS
            or not re.fullmatch(r"[1-9][0-9]{0,6}", fields["PR_NUMBER"])
            or not SHA.fullmatch(fields["PRODUCT_SHA"])):
        return None
    return fields


def ingest(db_path, comments, *, now=None):
    """Atomic batch; duplicate/restart safe. No comment can authorize work."""
    now = int(time.time() if now is None else now)
    if not isinstance(comments, list) or len(comments) > 5000:
        raise ValueError("bounded complete comment page set required")
    ids = [c.get("id") if isinstance(c, dict) else None for c in comments]
    if any(type(i) is not int or i <= 0 for i in ids) or len(ids) != len(set(ids)):
        raise ValueError("invalid or duplicated GitHub comment ids")
    inserted = conflicts = ignored = 0
    with sqlite3.connect(db_path, timeout=15) as db:
        db.execute("BEGIN IMMEDIATE")
        init(db)
        old = db.execute("SELECT last_comment_id FROM hub_cursor WHERE issue=?", (ISSUE,)).fetchone()
        cursor = old[0] if old else 0
        for c in sorted(comments, key=lambda c: c["id"]):
            cid = c["id"]
            if cid <= cursor:
                continue
            parsed = parse_request(c)
            author = (c.get("user") or {}).get("login")
            if parsed and isinstance(author, str) and re.fullmatch(r"[A-Za-z0-9-]{1,39}", author):
                row = db.execute("SELECT comment_id FROM hub_requests WHERE request_id=?",
                                 (parsed["REQUEST_ID"],)).fetchone()
                if row is None:
                    db.execute("""INSERT INTO hub_requests VALUES
                        (?,?,?,?,?,?,?,?,?,?)""", (
                        parsed["REQUEST_ID"], cid, author, parsed["FROM"],
                        parsed["TO"], parsed["TYPE"], int(parsed["PR_NUMBER"]),
                        parsed["PRODUCT_SHA"], "UNTRUSTED_INTAKE", now))
                    disposition = "STAGED_UNTRUSTED"
                    inserted += 1
                else:
                    disposition = "DUPLICATE_REQUEST_ID"
                    conflicts += 1
            else:
                disposition = "IGNORED_INVALID"
                ignored += 1
            db.execute("INSERT INTO hub_intake_audit VALUES (?,?,?)", (cid, disposition, now))
            cursor = cid
        db.execute("""INSERT INTO hub_cursor(issue,last_comment_id,updated_at)
            VALUES (?,?,?) ON CONFLICT(issue) DO UPDATE SET
            last_comment_id=excluded.last_comment_id,
            updated_at=excluded.updated_at""", (ISSUE, cursor, now))
    return {"state": "READ_ONLY_INTAKE", "inserted": inserted,
            "conflicts": conflicts, "ignored": ignored, "cursor": cursor,
            "executable": False, "qa_approved": False}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward Authorization to another host.


def fetch_comments(token, *, opener=None):
    """Fetch all pages before any DB writes; fail closed on partial response."""
    if not isinstance(token, str) or not token.strip():
        raise ValueError("read-only GitHub credential required")
    opener = opener or urllib.request.build_opener(NoRedirect)
    comments = []
    for page in range(1, 51):
        url = f"{API}?per_page=100&page={page}"
        request = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "hangeul-c-hub-intake-readonly"})
        with opener.open(request, timeout=15) as response:
            if response.geturl() != url:
                raise ValueError("unexpected GitHub API redirect")
            payload = json.loads(response.read(2_000_000))
        if not isinstance(payload, list) or len(payload) > 100:
            raise ValueError("unexpected GitHub comment page")
        comments.extend(payload)
        if len(payload) < 100:
            return comments
    raise ValueError("too many comment pages; fail closed")


def main():
    token_file = os.environ.get("HUB_GH_TOKEN_FILE", "")
    db_path = os.environ.get("HUB_DB_PATH", "")
    if not token_file or not db_path or not os.path.isabs(db_path):
        print(json.dumps({"state": "BLOCKED_CONFIG", "executable": False}))
        return 2
    try:
        token = Path(token_file).read_text().strip()
        result = ingest(db_path, fetch_comments(token))
    except Exception:
        # Never log token, arbitrary comment text or provider error body.
        print(json.dumps({"state": "READ_ONLY_SYNC_FAILED", "executable": False}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
