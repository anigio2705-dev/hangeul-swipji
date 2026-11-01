"""B/15 QA-only adversarial tests for C #264 exact product SHA 47fa2620618562f17d53591e34a7a441e34127df.

Synthetic, read-only provenance fixture. No B authenticated identity, no live
GitHub credential, no AI execution, no host deployment, no A READY.
"""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from cb_qa_tick import run_tick, LEASE_SECONDS, POLL_SECONDS
from test_cb_qa_evidence import positive_fixture, set_fail_proof, S, Q
from test_cb_qa_tick import rest_fixture


class IndependentExpiredLeaseFenceQA(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = str(Path(tmp.name) / "bqa-c264.sqlite3")
        self.fixture = positive_fixture()
        self.kw = dict(
            request_id="HUB-20261101-B-C264-RECHECK",
            source_pr_number=168, qa_pr_number=500, run_id=123,
            product_sha=S, qa_sha=Q, trusted_b_login="independent-b",
            token="synthetic-test-only", now=1000,
        )

    def poll(self, **changes):
        args = self.kw | changes
        args.setdefault("get_json", rest_fixture(self.fixture))
        args.setdefault(
            "get_text",
            lambda path: self.fixture["raw_job_logs"][1001]
            if path == "/actions/jobs/1001/logs" else None,
        )
        return run_tick(self.path, **args)

    def receipts(self):
        with sqlite3.connect(self.path) as db:
            present = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='cb_qa_receipts'"
            ).fetchone()
            return db.execute("SELECT COUNT(*) FROM cb_qa_receipts").fetchone()[0] if present else 0

    def tick_row(self):
        with sqlite3.connect(self.path) as db:
            return db.execute(
                "SELECT state,lease_owner,lease_until,next_check "
                "FROM cb_qa_ticks"
            ).fetchone()

    def fail_fixture(self):
        set_fail_proof(self.fixture)
        self.fixture["qa_reviews"][0]["state"] = "CHANGES_REQUESTED"
        self.fixture["qa_reviews"][0]["body"] = (
            f"HS_B_QA_VERDICT status=QA_FAIL product_sha={S} qa_sha={Q}"
        )

    def test_boundary_one_second_before_expiry_allows_verified_pass(self):
        self.assertEqual(self.poll(clock=lambda: 1000 + LEASE_SECONDS - 1)["state"],
                         "QA_PASS_VERIFIED")
        self.assertEqual(self.receipts(), 1)

    def test_exact_deadline_denies_pass_and_writes_no_receipt(self):
        result = self.poll(clock=lambda: 1000 + LEASE_SECONDS)
        self.assertEqual(result["state"], "EXPIRED_LEASE")
        self.assertEqual(self.receipts(), 0)
        self.assertEqual(self.tick_row(),
                         ("WAITING_B_EVIDENCE", None, 0, 1180 + POLL_SECONDS))

    def test_expiry_after_deadline_denies_fail_and_writes_no_receipt(self):
        self.fail_fixture()
        result = self.poll(clock=lambda: 1181)
        self.assertEqual(result["state"], "EXPIRED_LEASE")
        self.assertEqual(self.receipts(), 0)
        self.assertEqual(self.tick_row()[0:3],
                         ("WAITING_B_EVIDENCE", None, 0))

    def test_expired_poll_never_saves_fail_and_retries_only_after_next_check(self):
        self.fail_fixture()
        self.assertEqual(self.poll(clock=lambda: 1181)["state"], "EXPIRED_LEASE")
        self.assertEqual(self.poll(now=1420)["state"], "WAITING")
        self.assertEqual(self.receipts(), 0)
        self.assertEqual(self.poll(now=1421)["state"], "C_REWORK_REQUIRED")
        self.assertEqual(self.receipts(), 1)

    def test_expired_poll_no_receipt_even_if_github_fetch_fails(self):
        def network_error(_):
            raise RuntimeError("Bearer SECRET_DO_NOT_PERSIST")
        result = self.poll(get_json=network_error, clock=lambda: 1181)
        self.assertEqual(result["state"], "EXPIRED_LEASE")
        self.assertEqual(self.receipts(), 0)
        with sqlite3.connect(self.path) as db:
            detail = db.execute("SELECT detail FROM cb_qa_ticks").fetchone()[0]
        self.assertNotIn("SECRET_DO_NOT_PERSIST", detail)

    def test_lease_stolen_during_get_precedes_expiry_and_does_not_overwrite(self):
        getter = rest_fixture(self.fixture)
        changed = [False]
        def steal(path):
            if not changed[0]:
                changed[0] = True
                with sqlite3.connect(self.path) as db:
                    db.execute(
                        "UPDATE cb_qa_ticks SET lease_owner='new-owner',"
                        "lease_until=9999 WHERE request_id=? AND product_sha=?",
                        (self.kw["request_id"], S),
                    )
            return getter(path)
        result = self.poll(get_json=steal, clock=lambda: 1181)
        self.assertEqual(result["state"], "STALE_LEASE")
        self.assertEqual(self.receipts(), 0)
        self.assertEqual(self.tick_row()[1], "new-owner")

    def test_after_expired_poll_new_worker_can_recover_to_pass(self):
        self.assertEqual(self.poll(clock=lambda: 1181)["state"], "EXPIRED_LEASE")
        self.assertEqual(self.poll(now=1200)["state"], "WAITING")
        self.assertEqual(self.poll(now=1421)["state"], "QA_PASS_VERIFIED")
        self.assertEqual(self.receipts(), 1)
        self.assertEqual(self.poll(now=1500)["state"], "QA_PASS_VERIFIED")
        self.assertEqual(self.receipts(), 1)

    def test_expired_poll_never_claims_independent_identity_or_ready(self):
        self.assertEqual(self.poll(clock=lambda: 1181)["state"], "EXPIRED_LEASE")
        self.assertEqual(self.receipts(), 0)
        self.assertEqual(self.poll(now=1421, trusted_b_login="developer")["state"],
                         "WAITING_B_EVIDENCE")
        self.assertEqual(self.receipts(), 0)

    def test_invalid_pinned_sha_is_blocked_before_sqlite_creation(self):
        self.assertEqual(self.poll(product_sha="not-a-sha")["state"], "BLOCKED_CONFIG")
        self.assertFalse(Path(self.path).exists())


if __name__ == "__main__":
    unittest.main()
