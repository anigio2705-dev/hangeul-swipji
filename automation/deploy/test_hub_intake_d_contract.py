"""Additional C/D security regression tests; synthetic only, no network/AI calls."""
import os
import sqlite3
import tempfile
import unittest

from hub_request_intake import ingest, parse_request

SHA = "3c583f2b5d6c0ff19c9b75ccca150c5db1096b3e"
REQUEST_ID = "HUB-20261101-D-C-INTAKE-002"

def fixture(kind="D_REVIEW_REQUEST", author="shared-account", comment_id=6555695503):
    return {"id": comment_id, "user": {"login": author}, "body": (
        f"REQUEST_ID: {REQUEST_ID}\nFROM: D\nTO: C\nTYPE: {kind}\n"
        f"PR_NUMBER: 268\nPRODUCT_SHA: {SHA}\n")}

class TestDIntakeContract(unittest.TestCase):
    def test_reject_unrecognized_review_request(self):
        self.assertIsNone(parse_request(fixture("REVIEW_REQUEST")))

    def test_accept_d_review_request_as_untrusted_data(self):
        parsed = parse_request(fixture())
        self.assertEqual(parsed["TYPE"], "D_REVIEW_REQUEST")
        with tempfile.TemporaryDirectory() as directory:
            dbpath = os.path.join(directory, "hub.sqlite")
            result = ingest(dbpath, [fixture()], now=1)
            self.assertEqual(result["inserted"], 1)
            self.assertFalse(result["executable"])
            self.assertFalse(result["qa_approved"])
            with sqlite3.connect(dbpath) as db:
                self.assertEqual(db.execute("SELECT state FROM hub_requests WHERE request_id=?", (REQUEST_ID,)).fetchone()[0], "UNTRUSTED_INTAKE")

    def test_same_account_claimed_d_cannot_authorize(self):
        with tempfile.TemporaryDirectory() as directory:
            dbpath = os.path.join(directory, "hub.sqlite")
            result = ingest(dbpath, [fixture(author="shared-account")], now=2)
            self.assertFalse(result["executable"])
            with sqlite3.connect(dbpath) as db:
                author, role, state = db.execute("SELECT author,from_role,state FROM hub_requests").fetchone()
                self.assertEqual((author, role, state), ("shared-account", "D", "UNTRUSTED_INTAKE"))

    def test_restart_cursor_prevents_duplicate_intake(self):
        with tempfile.TemporaryDirectory() as directory:
            dbpath = os.path.join(directory, "hub.sqlite")
            self.assertEqual(ingest(dbpath, [fixture()], now=3)["inserted"], 1)
            self.assertEqual(ingest(dbpath, [fixture()], now=4)["inserted"], 0)
            with sqlite3.connect(dbpath) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM hub_requests").fetchone()[0], 1)
                self.assertEqual(db.execute("SELECT last_comment_id FROM hub_cursor WHERE issue=245").fetchone()[0], 6555695503)
                self.assertEqual(db.execute("SELECT disposition FROM hub_intake_audit WHERE comment_id=6555695503").fetchone()[0], "STAGED_UNTRUSTED")

if __name__ == "__main__":
    unittest.main()
