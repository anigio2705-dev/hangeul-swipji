"""B/15 independent QA-only security regressions for C #290 EXACT faa5856b.
Tests only: no production changes, no agent execution, no authenticated host claim.
"""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from cb_qa_verdict_store import accept_verdict
from cb_rework_outbox import pending, stage_verified_failure

PRODUCT_SHA = "a" * 40
QA_SHA = "b" * 40
REQUEST_ID = "HUB-20261101-B-C290-001"


class BQA290IndependentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "receipt.sqlite3"

    def seed_and_stage(self):
        result = accept_verdict(
            str(self.path), request_id=REQUEST_ID, pr_number=290,
            product_sha=PRODUCT_SHA, qa_sha=QA_SHA, verdict="QA_FAIL",
            evidence="synthetic B independent QA receipt, not an authenticated host",
            verified_by_b=True, ci_success=True, retry_count=0, now=1000)
        self.assertEqual(result, "C_FIXING")
        with sqlite3.connect(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            self.assertEqual(stage_verified_failure(
                db, request_id=REQUEST_ID, product_sha=PRODUCT_SHA, now=1001),
                "STAGED")

    def lookup(self, path=None, product_sha=PRODUCT_SHA, request_id=REQUEST_ID):
        return pending(str(self.path) if path is None else path,
                       request_id=request_id, product_sha=product_sha)

    def test_01_exact_receipt_is_non_executable(self):
        self.seed_and_stage()
        item = self.lookup()
        self.assertEqual(item["qa_sha"], QA_SHA)
        self.assertEqual(item["source_pr"], 290)
        self.assertIs(item["executable"], False)

    def test_02_parent_symlink_cannot_reach_valid_receipt(self):
        self.seed_and_stage()
        alias = self.root / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        self.assertIsNone(self.lookup(alias / self.path.name))
        self.assertIsNotNone(self.lookup())

    def test_03_ancestor_symlink_cannot_reach_valid_receipt(self):
        self.seed_and_stage()
        alias = self.root / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        self.assertIsNone(self.lookup(alias / "inner" / ".." / self.path.name))
        self.assertIsNotNone(self.lookup())

    def test_04_final_symlink_cannot_reach_valid_receipt(self):
        self.seed_and_stage()
        alias = self.root / "linked.sqlite3"
        alias.symlink_to(self.path)
        self.assertIsNone(self.lookup(alias))
        self.assertIsNotNone(self.lookup())

    def test_05_forged_sha_object_cannot_stage_or_create_schema(self):
        class Forged:
            def __str__(self):
                return PRODUCT_SHA
        with sqlite3.connect(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            self.assertEqual(stage_verified_failure(
                db, request_id=REQUEST_ID, product_sha=Forged()), "INVALID")
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM sqlite_master "
                "WHERE name='cb_rework_outbox'").fetchone()[0], 0)

    def test_06_pending_does_not_stringify_hostile_sha(self):
        class Hostile:
            def __str__(self):
                raise AssertionError("must never stringify untrusted SHA")
        self.seed_and_stage()
        self.assertIsNone(self.lookup(product_sha=Hostile()))
        self.assertIsNotNone(self.lookup())

    def test_07_revoked_receipt_does_not_authorize_lookup(self):
        self.seed_and_stage()
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE cb_qa_receipts SET qa_status='QA_PASS'")
        self.assertIsNone(self.lookup())

    def test_08_changed_qa_sha_does_not_authorize_lookup(self):
        self.seed_and_stage()
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE cb_qa_receipts SET qa_sha=?", ("c" * 40,))
        self.assertIsNone(self.lookup())

    def test_09_missing_db_remains_missing_after_read(self):
        self.assertFalse(self.path.exists())
        self.assertIsNone(self.lookup())
        self.assertFalse(self.path.exists())

    def test_10_empty_db_is_not_mutated_by_read(self):
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE unrelated(x INTEGER)")
        self.assertIsNone(self.lookup())
        with sqlite3.connect(self.path) as db:
            names = [x[0] for x in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")]
        self.assertEqual(names, ["unrelated"])

    def test_11_oversized_request_rejected_before_schema_write(self):
        with sqlite3.connect(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            self.assertEqual(stage_verified_failure(
                db, request_id="x" * 129, product_sha=PRODUCT_SHA), "INVALID")
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM sqlite_master "
                "WHERE name='cb_rework_outbox'").fetchone()[0], 0)

    def test_12_nontransactional_staging_is_denied(self):
        with sqlite3.connect(self.path) as db:
            with self.assertRaises(ValueError):
                stage_verified_failure(
                    db, request_id=REQUEST_ID, product_sha=PRODUCT_SHA)


if __name__ == "__main__":
    unittest.main()
