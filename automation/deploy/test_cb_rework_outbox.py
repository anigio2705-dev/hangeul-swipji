"""Synthetic rework outbox tests. Not a Codex call or independent B QA."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from cb_qa_verdict_store import accept_verdict
from cb_rework_outbox import pending, stage_verified_failure

S = "a" * 40
Q = "b" * 40
REQUEST = "HUB-20261101-C-002"


class VerifiedReworkOutboxTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = str(Path(tmp.name) / "rework.sqlite3")

    def seed(self, *, verdict="QA_FAIL", retry=0):
        return accept_verdict(
            self.path, request_id=REQUEST, pr_number=264,
            product_sha=S, qa_sha=Q, verdict=verdict,
            evidence="trusted synthetic B-only raw CI receipt",
            verified_by_b=True, ci_success=True, retry_count=retry, now=1000)

    def stage(self):
        with sqlite3.connect(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            return stage_verified_failure(
                db, request_id=REQUEST, product_sha=S, now=1001)

    def test_verified_fail_staged_exactly_once(self):
        self.assertEqual(self.seed(), "C_FIXING")
        self.assertEqual(self.stage(), "STAGED")
        self.assertEqual(self.stage(), "ALREADY_STAGED")
        event = pending(self.path, request_id=REQUEST, product_sha=S)
        self.assertEqual((event["source_pr"], event["qa_sha"]),
                         (264, Q))
        self.assertEqual(event["state"], "AWAIT_AUTHENTICATED_CODEX")
        self.assertIs(event["executable"], False)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM cb_rework_outbox").fetchone()[0], 1)

    def test_pass_cannot_stage_rework(self):
        self.assertEqual(self.seed(verdict="QA_PASS"), "AWAIT_A_REVIEW")
        self.assertEqual(self.stage(), "NOT_AUTHORIZED")
        self.assertIsNone(pending(self.path, request_id=REQUEST, product_sha=S))

    def test_retry_exhaustion_cannot_stage_rework(self):
        self.assertEqual(self.seed(retry=3), "BLOCKER_245")
        self.assertEqual(self.stage(), "NOT_AUTHORIZED")

    def test_no_verified_receipt_cannot_stage_rework(self):
        with sqlite3.connect(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            # Ensure the receipt table exists but contains no verdict.
            db.execute("""CREATE TABLE cb_qa_receipts (
                request_id TEXT, product_sha TEXT, pr_number INTEGER,
                qa_sha TEXT, qa_status TEXT, evidence TEXT,
                retry_count INTEGER, next_action TEXT, updated_at INTEGER)""")
            self.assertEqual(stage_verified_failure(
                db, request_id=REQUEST, product_sha=S), "NOT_VERIFIED")

    def test_transaction_rollback_removes_receipt_and_outbox(self):
        # Create schemas BEFORE the transaction so a rollback preserves
        # the tables while discarding both the receipt and staged event.
        from cb_qa_verdict_store import init as init_receipts
        from cb_rework_outbox import init as init_outbox
        with sqlite3.connect(self.path) as db:
            init_receipts(db)
            init_outbox(db)
        with sqlite3.connect(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            self.assertEqual(accept_verdict(
                self.path, request_id=REQUEST, pr_number=264,
                product_sha=S, qa_sha=Q, verdict="QA_FAIL",
                evidence="synthetic", verified_by_b=True, ci_success=True,
                db=db), "C_FIXING")
            self.assertEqual(stage_verified_failure(
                db, request_id=REQUEST, product_sha=S), "STAGED")
            db.rollback()
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM cb_rework_outbox").fetchone()[0], 0)
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM cb_qa_receipts").fetchone()[0], 0)

    def test_untrusted_or_mismatched_sha_does_not_stage(self):
        self.assertEqual(self.seed(), "C_FIXING")
        self.assertEqual(self.stage(), "STAGED")
        self.assertEqual(pending(
            self.path, request_id=REQUEST, product_sha="c" * 40), None)
        with sqlite3.connect(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            self.assertEqual(stage_verified_failure(
                db, request_id=REQUEST, product_sha="invalid"), "INVALID")
            db.execute("""UPDATE cb_rework_outbox SET qa_sha=?
                WHERE request_id=? AND product_sha=?""",
                ("c" * 40, REQUEST, S))
            self.assertEqual(stage_verified_failure(
                db, request_id=REQUEST, product_sha=S), "CONFLICT")

    def test_pending_missing_database_never_creates_schema(self):
        self.assertFalse(Path(self.path).exists())
        self.assertIsNone(pending(self.path, request_id=REQUEST, product_sha=S))
        self.assertFalse(Path(self.path).exists())

    def test_pending_requires_receipt_to_match_outbox(self):
        self.assertEqual(self.seed(), "C_FIXING")
        self.assertEqual(self.stage(), "STAGED")
        self.assertIsNotNone(pending(self.path, request_id=REQUEST, product_sha=S))
        # A stale/altered outbox must not become a worker authorization.
        for column, changed in (
            ("qa_sha", "c" * 40),
            ("pr_number", 999),
            ("qa_status", "QA_PASS"),
            ("next_action", "BLOCKER_245"),
        ):
            with self.subTest(column=column):
                with sqlite3.connect(self.path) as db:
                    original = db.execute(
                        f"SELECT {column} FROM cb_qa_receipts WHERE request_id=? AND product_sha=?",
                        (REQUEST, S)).fetchone()[0]
                    db.execute(
                        f"UPDATE cb_qa_receipts SET {column}=? WHERE request_id=? AND product_sha=?",
                        (changed, REQUEST, S))
                self.assertIsNone(pending(self.path, request_id=REQUEST, product_sha=S))
                with sqlite3.connect(self.path) as db:
                    db.execute(
                        f"UPDATE cb_qa_receipts SET {column}=? WHERE request_id=? AND product_sha=?",
                        (original, REQUEST, S))
                self.assertIsNotNone(pending(self.path, request_id=REQUEST, product_sha=S))
        with sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM cb_qa_receipts WHERE request_id=? AND product_sha=?",
                       (REQUEST, S))
        self.assertIsNone(pending(self.path, request_id=REQUEST, product_sha=S))

    def test_requires_existing_transaction(self):
        with sqlite3.connect(self.path) as db:
            with self.assertRaises(ValueError):
                stage_verified_failure(db, request_id=REQUEST, product_sha=S)


if __name__ == "__main__":
    unittest.main()
