"""B/15 independent QA-only trust-boundary regressions for C #269 repaired exact f127bcb1203806cafe90e9a71d1baf956f6c5adb.

Recheck original #265 failures against new C #269 exact SHA. No host,
Codex, credentials, real PR authorization, operating DB or payment activity.
"""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from cb_qa_verdict_store import accept_verdict
from cb_rework_outbox import pending, stage_verified_failure

PRODUCT_SHA = "a" * 40
QA_SHA = "b" * 40
REQUEST_ID = "HUB-20261101-B-C265-TRUST"


class IndependentOutboxTrustBoundaryQA(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db_path = str(Path(temp.name) / "qa-only.sqlite3")

    def seed_verified_fail_and_stage(self):
        result = accept_verdict(
            self.db_path, request_id=REQUEST_ID, pr_number=264,
            product_sha=PRODUCT_SHA, qa_sha=QA_SHA, verdict="QA_FAIL",
            evidence="synthetic verified fixture only",
            verified_by_b=True, ci_success=True, retry_count=0, now=1000,
        )
        self.assertEqual(result, "C_FIXING")
        with sqlite3.connect(self.db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            self.assertEqual(stage_verified_failure(
                db, request_id=REQUEST_ID, product_sha=PRODUCT_SHA, now=1001),
                "STAGED")

    def test_valid_immutable_fail_receipt_is_nonexecutable(self):
        self.seed_verified_fail_and_stage()
        event = pending(self.db_path, request_id=REQUEST_ID,
                        product_sha=PRODUCT_SHA)
        self.assertIsNotNone(event)
        self.assertEqual(event["source_pr"], 264)
        self.assertEqual(event["qa_sha"], QA_SHA)
        self.assertIs(event["executable"], False)

    def test_missing_database_read_only_lookup_does_not_create_file(self):
        self.assertFalse(Path(self.db_path).exists())
        self.assertIsNone(pending(self.db_path, request_id=REQUEST_ID,
                                  product_sha=PRODUCT_SHA))
        self.assertFalse(Path(self.db_path).exists(),
                         "read-only pending() must not create a new SQLite DB")

    def test_missing_outbox_schema_read_only_lookup_does_not_create_table(self):
        with sqlite3.connect(self.db_path) as db:
            db.execute("CREATE TABLE unrelated (id INTEGER)")
        self.assertIsNone(pending(self.db_path, request_id=REQUEST_ID,
                                  product_sha=PRODUCT_SHA))
        with sqlite3.connect(self.db_path) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name='cb_rework_outbox'"
            ).fetchone()[0], 0, "read-only pending() must not initialize schema")

    def test_missing_verified_receipt_cannot_return_old_outbox_event(self):
        self.seed_verified_fail_and_stage()
        with sqlite3.connect(self.db_path) as db:
            db.execute("DELETE FROM cb_qa_receipts WHERE request_id=?",
                       (REQUEST_ID,))
        self.assertIsNone(pending(self.db_path, request_id=REQUEST_ID,
                                  product_sha=PRODUCT_SHA),
                          "outbox without matching immutable QA_FAIL is untrusted")

    def test_changed_receipt_qa_sha_cannot_return_stale_outbox_event(self):
        self.seed_verified_fail_and_stage()
        with sqlite3.connect(self.db_path) as db:
            db.execute("UPDATE cb_qa_receipts SET qa_sha=? WHERE request_id=?",
                       ("c" * 40, REQUEST_ID))
        self.assertIsNone(pending(self.db_path, request_id=REQUEST_ID,
                                  product_sha=PRODUCT_SHA),
                          "pending() must bind outbox to exact receipt QA SHA")

    def test_changed_receipt_verdict_cannot_return_old_rework_event(self):
        self.seed_verified_fail_and_stage()
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "UPDATE cb_qa_receipts SET qa_status='QA_PASS',"
                "next_action='AWAIT_A_REVIEW' WHERE request_id=?",
                (REQUEST_ID,))
        self.assertIsNone(pending(self.db_path, request_id=REQUEST_ID,
                                  product_sha=PRODUCT_SHA),
                          "pending() must recheck QA_FAIL/C_FIXING trust gate")


if __name__ == "__main__":
    unittest.main()
