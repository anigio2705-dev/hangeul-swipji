"""Independent negative-case tests for durable worker handoff (NO AI calls)."""
import os
import tempfile
import unittest

from continuous_dispatcher import MARKER, QueueIntegrityError
from work_request_worker import DurableWorkStore


class WorkerStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "work.sqlite3")
        self.a = DurableWorkStore(self.path)
        self.work = {"number": 101, "title": MARKER + " Central task", "state": "open"}

    def tearDown(self):
        self.a.close()
        self.temp.cleanup()

    def test_persists_after_restart(self):
        self.a.ingest(self.work, now=100)
        self.a.close()
        self.a = DurableWorkStore(self.path)
        self.assertEqual(self.a.snapshot(101)["status"], "PENDING")

    def test_duplicate_delivery_is_idempotent(self):
        self.a.ingest(self.work, now=100)
        self.a.ingest(self.work, now=101)
        self.assertEqual(self.a.claim("central", now=102)["attempt"], 1)
        self.assertIsNone(self.a.claim("other", now=103))

    def test_changed_title_same_issue_rejected(self):
        self.a.ingest(self.work, now=100)
        with self.assertRaises(QueueIntegrityError):
            self.a.ingest({**self.work, "title": MARKER + " changed"}, now=101)

    def test_pull_request_rejected(self):
        with self.assertRaises(ValueError):
            self.a.ingest({**self.work, "pull_request": {}}, now=100)

    def test_two_connections_cannot_claim_same_lease(self):
        self.a.ingest(self.work, now=100)
        b = DurableWorkStore(self.path)
        try:
            self.assertEqual(self.a.claim("central", now=101)["issue"], 101)
            self.assertIsNone(b.claim("qa", now=101))
        finally:
            b.close()

    def test_expired_lease_recovered_after_restart(self):
        self.a.ingest(self.work, now=100)
        self.a.claim("central", now=101, lease_seconds=30)
        self.a.close()
        self.a = DurableWorkStore(self.path)
        self.assertIsNone(self.a.claim("other", now=130))
        self.assertEqual(self.a.claim("other", now=131)["attempt"], 2)
        self.assertEqual(self.a.snapshot(101)["lease_owner"], "other")

    def test_wrong_owner_cannot_heartbeat_or_complete(self):
        self.a.ingest(self.work, now=100)
        self.a.claim("central", now=101)
        self.assertFalse(self.a.heartbeat(101, "other", now=102))
        self.assertFalse(self.a.finish(101, "other", "https://example.test/proof", now=102))
        self.assertEqual(self.a.snapshot(101)["status"], "LEASED")

    def test_heartbeat_extends_live_lease(self):
        self.a.ingest(self.work, now=100)
        self.a.claim("central", now=101, lease_seconds=30)
        self.assertTrue(self.a.heartbeat(101, "central", now=120, lease_seconds=300))
        self.assertIsNone(self.a.claim("other", now=131))

    def test_completion_is_report_only(self):
        self.a.ingest(self.work, now=100)
        self.a.claim("central", now=101)
        self.assertTrue(self.a.finish(101, "central", "run=123 sha=abc QA pending", now=102))
        self.assertEqual(self.a.snapshot(101)["status"], "REPORTED")
        self.assertIsNone(self.a.claim("other", now=2000))

    def test_expired_owner_cannot_complete(self):
        self.a.ingest(self.work, now=100)
        self.a.claim("central", now=101, lease_seconds=30)
        self.assertFalse(self.a.finish(101, "central", "run=123 sha=abc", now=131))

    def test_fail_retry_backoff_then_block(self):
        self.a.ingest(self.work, now=100)
        for n, t in enumerate((101, 162, 283), start=1):
            claimed = self.a.claim("central", now=t)
            self.assertEqual(claimed["attempt"], n)
            self.assertTrue(self.a.fail(101, "central", now=t + 1))
            self.assertEqual(self.a.snapshot(101)["status"],
                             "BLOCKED" if n == 3 else "PENDING")
        self.assertIsNone(self.a.claim("central", now=10000))

    def test_crash_after_third_claim_blocks_on_expiry(self):
        self.a.ingest(self.work, now=100)
        for n, t in enumerate((101, 162), start=1):
            self.assertEqual(self.a.claim("central", now=t)["attempt"], n)
            self.assertTrue(self.a.fail(101, "central", now=t + 1))
        self.assertEqual(self.a.claim("central", now=283, lease_seconds=30)["attempt"], 3)
        self.assertIsNone(self.a.claim("other", now=314))
        self.assertEqual(self.a.snapshot(101)["status"], "BLOCKED")

    def test_invalid_worker_or_proof_rejected(self):
        self.a.ingest(self.work, now=100)
        with self.assertRaises(ValueError):
            self.a.claim("", now=101)
        self.a.claim("central", now=101)
        with self.assertRaises(ValueError):
            self.a.finish(101, "central", "", now=102)

    def test_worker_is_not_a_chatgpt_adapter(self):
        self.a.ingest(self.work, now=100)
        self.assertNotIn("READY", self.a.snapshot(101))
        self.assertNotIn("agent_invoked", self.a.snapshot(101))


if __name__ == "__main__":
    unittest.main()
