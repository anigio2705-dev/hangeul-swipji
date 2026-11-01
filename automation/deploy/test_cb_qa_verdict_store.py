"""Regression tests for fail-closed C/B exact-SHA verdict receipts."""
import tempfile
import unittest
from pathlib import Path
from cb_qa_verdict_store import accept_verdict, pending_fix

class VerdictTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / "durable.sqlite3")
        self.kw = dict(request_id="HUB-20261101-C-001", pr_number=168,
                       product_sha="a"*40, qa_sha="b"*40,
                       verdict="QA_FAIL", evidence="B QA run 123: traversal",
                       verified_by_b=True, ci_success=True, retry_count=0)
    def call(self, **changes):
        return accept_verdict(self.path, **(self.kw | changes))
    def test_requires_external_b_verification(self):
        self.assertEqual(self.call(verified_by_b=False), "UNVERIFIED")
        self.assertEqual(self.call(ci_success=False), "UNVERIFIED")
        self.assertEqual(self.call(qa_sha="invalid"), "UNVERIFIED")
        self.assertIsNone(pending_fix(self.path, self.kw["request_id"], "a"*40))
    def test_fail_is_durable_and_recoverable(self):
        self.assertEqual(self.call(), "C_FIXING")
        self.assertEqual(pending_fix(self.path, self.kw["request_id"], "a"*40)["NEXT_ACTION"], "C_FIXING")
        self.assertEqual(self.call(), "DUPLICATE")
        self.assertEqual(self.call(verdict="QA_PASS"), "CONFLICT")
    def test_new_sha_is_separate_verification(self):
        self.assertEqual(self.call(), "C_FIXING")
        self.assertEqual(self.call(product_sha="c"*40, qa_sha="d"*40, verdict="QA_PASS"), "AWAIT_A_REVIEW")
        self.assertEqual(pending_fix(self.path, self.kw["request_id"], "a"*40)["NEXT_ACTION"], "C_FIXING")
        self.assertIsNone(pending_fix(self.path, self.kw["request_id"], "c"*40))
    def test_retry_limit_escalates(self):
        self.assertEqual(self.call(retry_count=3), "BLOCKER_245")
        self.assertEqual(pending_fix(self.path, self.kw["request_id"], "a"*40)["NEXT_ACTION"], "BLOCKER_245")

if __name__ == "__main__":
    unittest.main()
