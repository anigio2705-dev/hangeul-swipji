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

    def test_closed_issue_rejected(self):
        with self.assertRaises(ValueError):
            self.a.ingest({**self.work, "state": "closed"}, now=100)

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
        recovered = self.a.claim("other", now=131)
        self.assertEqual(recovered["attempt"], 2)
        self.assertEqual(self.a.snapshot(101)["lease_owner"], recovered["owner"])

    def test_wrong_owner_cannot_heartbeat_or_complete(self):
        self.a.ingest(self.work, now=100)
        self.a.claim("central", now=101)
        self.assertFalse(self.a.heartbeat(101, "other", now=102))
        self.assertFalse(self.a.finish(101, "other", "https://example.test/proof", now=102))
        self.assertEqual(self.a.snapshot(101)["status"], "LEASED")

    def test_heartbeat_extends_live_lease(self):
        self.a.ingest(self.work, now=100)
        claim = self.a.claim("central", now=101, lease_seconds=30)
        self.assertTrue(self.a.heartbeat(101, claim["owner"], now=120, lease_seconds=300))
        self.assertIsNone(self.a.claim("other", now=131))

    def test_completion_is_report_only(self):
        self.a.ingest(self.work, now=100)
        claim = self.a.claim("central", now=101)
        self.assertTrue(self.a.finish(101, claim["owner"], "run=123 sha=abc QA pending", now=102))
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
            self.assertTrue(self.a.fail(101, claimed["owner"], now=t + 1))
            self.assertEqual(self.a.snapshot(101)["status"],
                             "BLOCKED" if n == 3 else "PENDING")
        self.assertIsNone(self.a.claim("central", now=10000))

    def test_crash_after_third_claim_blocks_on_expiry(self):
        self.a.ingest(self.work, now=100)
        for n, t in enumerate((101, 162), start=1):
            claim = self.a.claim("central", now=t)
            self.assertEqual(claim["attempt"], n)
            self.assertTrue(self.a.fail(101, claim["owner"], now=t + 1))
        self.assertEqual(self.a.claim("central", now=283, lease_seconds=30)["attempt"], 3)
        self.assertIsNone(self.a.claim("other", now=314))
        self.assertEqual(self.a.snapshot(101)["status"], "BLOCKED")

    def test_qa15_same_name_reclaim_cannot_mutate_new_lease(self):
        self.a.ingest(self.work, now=100)
        stale = self.a.claim("central", now=101, lease_seconds=30)
        current = self.a.claim("central", now=131, lease_seconds=30)
        self.assertEqual(current["attempt"], 2)
        self.assertNotEqual(stale["owner"], current["owner"])
        self.assertFalse(self.a.heartbeat(101, stale["owner"], now=132))
        self.assertFalse(self.a.finish(101, stale["owner"], "run=stale sha=abc", now=132))
        self.assertFalse(self.a.fail(101, stale["owner"], now=132))
        self.assertEqual(self.a.snapshot(101)["lease_owner"], current["owner"])
        self.assertEqual(self.a.snapshot(101)["status"], "LEASED")
        self.assertTrue(self.a.finish(101, current["owner"], "run=current sha=def", now=132))
        self.assertEqual(self.a.snapshot(101)["status"], "REPORTED")

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


    def test_audit_stale_lease_after_restart_and_same_name_reclaim(self):
        """A prior process must not finish, heartbeat or fail a newer lease."""
        self.a.ingest(self.work, now=100)
        old = self.a.claim("central", now=101, lease_seconds=30)
        self.a.close()
        self.a = DurableWorkStore(self.path)
        new = self.a.claim("central", now=131, lease_seconds=30)
        self.assertEqual(new["attempt"], 2)
        self.assertNotEqual(old["owner"], new["owner"])
        self.assertFalse(self.a.heartbeat(101, old["owner"], now=132))
        self.assertFalse(self.a.fail(101, old["owner"], now=132))
        self.assertFalse(self.a.finish(101, old["owner"], "run=old sha=old", now=132))
        self.assertEqual(self.a.snapshot(101)["lease_owner"], new["owner"])
        self.assertTrue(self.a.finish(101, new["owner"], "run=new sha=new", now=132))

    def test_audit_closed_request_is_not_executable_after_reconciliation(self):
        """Closing a GitHub work issue must cancel its pending execution."""
        self.a.ingest(self.work, now=100)
        # The next GitHub open-issue poll omits this closed request. Current
        # main() ingests only pending(open_issues), without reconciling closures.
        from continuous_dispatcher import pending
        self.assertEqual(pending([{**self.work, "state": "closed"}]), [])
        self.assertIsNotNone(self.a.snapshot(101))
        self.assertIsNone(self.a.claim("central", now=102),
                          "QA safety FAIL: previously queued but now-closed issue still executable")


if __name__ == "__main__":
    unittest.main()
