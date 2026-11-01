"""Ephemeral CI proof: public GitHub Issue #245 GET -> local SQLite, no credentials.

This proves a real network fetch on a GitHub Actions runner, not deployment to
an always-on host. It never authorizes QA, READY, AI execution or pushes.
"""
import json
import os
import sqlite3
import tempfile
import urllib.request

from hub_request_intake import API, ISSUE, NoRedirect, ingest, parse_request

COMMENT_ID = 6555695503
REQUEST_ID = "HUB-20261101-D-C-INTAKE-002"
PRODUCT_SHA = "3c583f2b5d6c0ff19c9b75ccca150c5db1096b3e"


def fetch_public_comments():
    opener = urllib.request.build_opener(NoRedirect)
    result = []
    for page in range(1, 51):
        url = f"{API}?per_page=100&page={page}"
        request = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "hangeul-c-ephemeral-intake-proof"})
        with opener.open(request, timeout=15) as response:
            if response.geturl() != url:
                raise ValueError("redirect refused")
            batch = json.loads(response.read(2_000_000))
        if not isinstance(batch, list) or len(batch) > 100:
            raise ValueError("incomplete or invalid GitHub comment page")
        result.extend(batch)
        if len(batch) < 100:
            return result
    raise ValueError("comment pagination limit exceeded")


def main():
    comments = fetch_public_comments()
    matched = [c for c in comments if c.get("id") == COMMENT_ID]
    if len(matched) != 1:
        raise SystemExit("BLOCKED: exact GitHub comment missing")
    parsed = parse_request(matched[0])
    if (not parsed or parsed["REQUEST_ID"] != REQUEST_ID
            or parsed["PRODUCT_SHA"] != PRODUCT_SHA
            or parsed["TYPE"] != "D_REVIEW_REQUEST"
            or parsed["FROM"] != "D" or parsed["TO"] != "C"):
        raise SystemExit("BLOCKED: invalid D request metadata")
    with tempfile.TemporaryDirectory(prefix="hangeul-intake-") as directory:
        path = os.path.join(directory, "ephemeral.sqlite3")
        first = ingest(path, comments)
        with sqlite3.connect(path) as db:
            row = db.execute(
                "SELECT comment_id,state FROM hub_requests WHERE request_id=?",
                (REQUEST_ID,)).fetchone()
            audit = db.execute(
                "SELECT disposition FROM hub_intake_audit WHERE comment_id=?",
                (COMMENT_ID,)).fetchone()
            cursor = db.execute(
                "SELECT last_comment_id FROM hub_cursor WHERE issue=?",
                (ISSUE,)).fetchone()
        if (row != (COMMENT_ID, "UNTRUSTED_INTAKE")
                or audit != ("STAGED_UNTRUSTED",)
                or not cursor or cursor[0] < COMMENT_ID):
            raise SystemExit("BLOCKED: SQLite receipt mismatch")
        second = ingest(path, comments)
        with sqlite3.connect(path) as db:
            count = db.execute(
                "SELECT COUNT(*) FROM hub_requests WHERE request_id=?",
                (REQUEST_ID,)).fetchone()[0]
        if second["inserted"] != 0 or count != 1:
            raise SystemExit("BLOCKED: replay was not idempotent")
    print(json.dumps({
        "state": "EPHEMERAL_CI_LIVE_GET_SQLITE_PASS",
        "issue": ISSUE, "comment_id": COMMENT_ID, "request_id": REQUEST_ID,
        "row_state": row[1], "audit": audit[0], "cursor": cursor[0],
        "initial_inserted": first["inserted"], "replay_inserted": second["inserted"],
        "identity_verified": False, "executable": False,
        "persistent_host_proven": False, "sqlite_lifetime": "EPHEMERAL_JOB"
    }, sort_keys=True))


if __name__ == "__main__":
    main()
