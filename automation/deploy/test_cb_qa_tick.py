"""Synthetic controller tests; passing these is NOT independent B QA or host proof."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from cb_qa_tick import run_tick
from cb_qa_verdict_store import accept_verdict, pending_fix
from test_cb_qa_evidence import fixture, S, Q


def rest_fixture(data):
    def get(path):
        if path == "/pulls/168":
            return data["source_pr"]
        if path == "/pulls/500":
            return data["qa_pr"]
        if path.startswith("/pulls/500/files?"):
            return data["qa_files"]
        if path == "/actions/runs/123":
            return data["qa_run"]
        if path.startswith("/pulls/500/reviews?"):
            return data["qa_reviews"]
        raise AssertionError(path)
    return get


class DurableTickTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = str(Path(self.temp.name) / "cb.sqlite3")
        self.data = fixture()
        self.kw = dict(
            request_id="HUB-20261101-C-002",
            source_pr_number=168, qa_pr_number=500, run_id=123,
            product_sha=S, qa_sha=Q, trusted_b_login="independent-b",
            token="synthetic-test-only", now=1000)

    def tick(self, **changes):
        kw = self.kw | changes
        kw.setdefault("get_json", rest_fixture(self.data))
        return run_tick(self.db, **kw)

    def test_verified_pass_durable_and_idempotent(self):
        self.assertEqual(self.tick()["state"], "QA_PASS_VERIFIED")
        self.assertEqual(self.tick(now=1240)["state"], "QA_PASS_VERIFIED")
        with sqlite3.connect(self.db) as db:
            rows = db.execute("SELECT qa_status,next_action FROM cb_qa_receipts").fetchall()
        self.assertEqual(rows, [("QA_PASS", "AWAIT_A_REVIEW")])

    def test_verified_fail_requires_rework_but_does_not_execute(self):
        self.data["qa_run"]["conclusion"] = "failure"
        self.data["qa_reviews"][0]["state"] = "CHANGES_REQUESTED"
        self.data["qa_reviews"][0]["body"] = (
            f"HS_B_QA_VERDICT status=QA_FAIL product_sha={S} qa_sha={Q}")
        self.assertEqual(self.tick()["state"], "C_REWORK_REQUIRED")
        self.assertEqual(pending_fix(self.db, self.kw["request_id"], S)["NEXT_ACTION"], "C_FIXING")
        self.assertEqual(self.tick(now=1240)["state"], "C_REWORK_REQUIRED")

    def test_unverified_review_is_waiting_not_failure(self):
        self.data["qa_reviews"] = []
        self.assertEqual(self.tick()["state"], "WAITING_B_EVIDENCE")
        self.assertEqual(self.tick(now=1100)["state"], "WAITING")
        self.data["qa_reviews"] = fixture()["qa_reviews"]
        self.assertEqual(self.tick(now=1240)["state"], "QA_PASS_VERIFIED")

    def test_same_account_review_cannot_be_accepted(self):
        self.assertEqual(self.tick(trusted_b_login="developer")["state"], "WAITING_B_EVIDENCE")
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='cb_qa_receipts'").fetchone()[0], 0)

    def test_stale_qa_run_is_not_accepted(self):
        self.data["qa_run"]["head_sha"] = "c" * 40
        self.assertEqual(self.tick()["state"], "WAITING_B_EVIDENCE")

    def test_network_error_never_leaks_exception_or_marks_fail(self):
        def bad_get(_):
            raise RuntimeError("Bearer SUPERSECRET SHOULD NEVER LOG")
        result = self.tick(get_json=bad_get)
        self.assertEqual(result["state"], "WAITING_B_EVIDENCE")
        self.assertNotIn("SUPERSECRET", str(result))
        with sqlite3.connect(self.db) as db:
            detail = db.execute("SELECT detail FROM cb_qa_ticks").fetchone()[0]
        self.assertNotIn("SUPERSECRET", detail)

    def test_lease_blocks_concurrent_poll_and_recovers_after_expiry(self):
        self.data["qa_reviews"] = []
        self.assertEqual(self.tick()["state"], "WAITING_B_EVIDENCE")
        with sqlite3.connect(self.db) as db:
            db.execute("""UPDATE cb_qa_ticks SET state='RUNNING',
                lease_owner='other',lease_until=2000,next_check=0""")
        self.assertEqual(self.tick(now=1100)["state"], "RUNNING")
        self.data["qa_reviews"] = fixture()["qa_reviews"]
        self.assertEqual(self.tick(now=2000)["state"], "QA_PASS_VERIFIED")

    def test_pinned_qa_sha_cannot_silently_change(self):
        self.data["qa_reviews"] = []
        self.assertEqual(self.tick()["state"], "WAITING_B_EVIDENCE")
        self.assertEqual(self.tick(now=1240, qa_sha="c" * 40)["state"], "BLOCKED_CONFIG")

    def test_missing_identity_and_invalid_input_do_not_fetch(self):
        self.assertEqual(self.tick(token="")["state"], "BLOCKED_CONFIG")
        self.assertEqual(self.tick(source_pr_number=True)["state"], "BLOCKED_CONFIG")
        self.assertEqual(self.tick(product_sha="invalid")["state"], "BLOCKED_CONFIG")

    def test_retry_limit_uses_durable_prior_failures(self):
        for i in range(3):
            self.assertEqual(accept_verdict(
                self.db, request_id=self.kw["request_id"], pr_number=168,
                product_sha="cde"[i] * 40,
                qa_sha="fed"[i] * 40, verdict="QA_FAIL",
                evidence=f"prior B QA {i}", verified_by_b=True,
                ci_success=True, retry_count=i), "C_FIXING")
        self.data["qa_run"]["conclusion"] = "failure"
        self.data["qa_reviews"][0]["state"] = "CHANGES_REQUESTED"
        self.data["qa_reviews"][0]["body"] = (
            f"HS_B_QA_VERDICT status=QA_FAIL product_sha={S} qa_sha={Q}")
        self.assertEqual(self.tick()["state"], "BLOCKED_245")

    def _steal_lease_during_fetch(self):
        # Deterministically emulate a new tick reclaiming the lease while
        # the old poll is still performing read-only GitHub GETs.
        getter = rest_fixture(self.data)
        stolen = [False]
        def get(path):
            if not stolen[0]:
                stolen[0] = True
                with sqlite3.connect(self.db) as db:
                    db.execute(
                        "UPDATE cb_qa_ticks SET lease_owner='newer', "
                        "lease_until=9999 WHERE request_id=? AND product_sha=?",
                        (self.kw["request_id"], S))
            return getter(path)
        return get

    def test_stale_pass_cannot_insert_receipt(self):
        result = self.tick(get_json=self._steal_lease_during_fetch())
        self.assertEqual(result["state"], "STALE_LEASE")
        with sqlite3.connect(self.db) as db:
            if db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='cb_qa_receipts'").fetchone():
                self.assertEqual(db.execute(
                    "SELECT COUNT(*) FROM cb_qa_receipts").fetchone()[0], 0)
            self.assertEqual(db.execute(
                "SELECT lease_owner FROM cb_qa_ticks").fetchone()[0], "newer")

    def test_stale_fail_cannot_insert_rework_receipt(self):
        self.data["qa_run"]["conclusion"] = "failure"
        self.data["qa_reviews"][0]["state"] = "CHANGES_REQUESTED"
        self.data["qa_reviews"][0]["body"] = (
            f"HS_B_QA_VERDICT status=QA_FAIL product_sha={S} qa_sha={Q}")
        result = self.tick(get_json=self._steal_lease_during_fetch())
        self.assertEqual(result["state"], "STALE_LEASE")
        with sqlite3.connect(self.db) as db:
            if db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='cb_qa_receipts'").fetchone():
                self.assertEqual(db.execute(
                    "SELECT COUNT(*) FROM cb_qa_receipts").fetchone()[0], 0)
            self.assertEqual(db.execute(
                "SELECT lease_owner FROM cb_qa_ticks").fetchone()[0], "newer")

    def test_no_a_ready_or_external_side_effects(self):
        result = self.tick()
        self.assertEqual(result["state"], "QA_PASS_VERIFIED")
        self.assertNotIn("READY", result["state"])
        self.assertEqual(result["detail"], "QA_PASS awaits A decision")


if __name__ == "__main__":
    unittest.main()
