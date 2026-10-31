"""15-team independent exact-SHA negative QA, NOT central product code.
Central base: 99adfa4035fa88844524d6b1b190175b543f282c
QA correlation ID: QA15-20261031T0212Z-PR162-99ADFA
"""
import io
import os
import tempfile
import unittest
from datetime import datetime, timezone
from urllib.error import HTTPError
from continuous_dispatcher import MARKER, QueueIntegrityError, list_open_issues, plan, request
from work_request_worker import DurableWorkStore

BASE_SHA = "99adfa4035fa88844524d6b1b190175b543f282c"
NOW = datetime(2026, 10, 31, 11, 0, tzinfo=timezone.utc)

def work(n=123, **changes):
    row = {"number": n, "title": MARKER+" QA independent",
           "state": "open", "created_at": "2026-10-31T10:30:00Z"}
    row.update(changes)
    return row

class IndependentWatchdog(unittest.TestCase):
    def test_more_than_100_and_last_page(self):
        seen = []
        def fetch(path, token):
            seen.append(path)
            if path.endswith("page=1"):
                return [work(i, title="other") for i in range(100)]
            if path.endswith("page=2"):
                return [work(101, title="other") for _ in range(49)] + [work(150)]
            raise AssertionError("unexpected page")
        rows = list_open_issues("a/b", "token", fetch=fetch)
        self.assertEqual(len(rows), 150)
        self.assertEqual(len(seen), 2)
        self.assertEqual(plan(rows, now=NOW)["action"], "wait")

    def test_page_limit_blocks_unknown_remaining_items(self):
        with self.assertRaises(QueueIntegrityError):
            list_open_issues("a/b", "token", max_pages=1,
                             fetch=lambda path, token: [work(i, title="other") for i in range(100)])

    def test_duplicate_open_work_blocks(self):
        self.assertEqual(plan([work(1), work(2)], now=NOW)["action"], "blocked")

    def test_old_unprocessed_work_stale(self):
        self.assertEqual(plan([work(created_at="2026-10-31T09:00:00Z")], now=NOW)["action"], "stale")

    def test_pr_is_not_work(self):
        self.assertEqual(plan([work(pull_request={})], now=NOW)["action"], "create")

    def test_forbidden_does_not_retry(self):
        calls = []
        def opener(req, timeout):
            calls.append(1)
            raise HTTPError(req.full_url, 403, "forbidden", {}, None)
        with self.assertRaises(HTTPError):
            request("/repos/a/b/issues", "secret", opener=opener, sleeper=lambda s: None)
        self.assertEqual(len(calls), 1)

    def test_rate_limit_retries(self):
        calls = []
        def opener(req, timeout):
            calls.append(1)
            if len(calls) == 1:
                raise HTTPError(req.full_url, 429, "rate", {}, None)
            return io.BytesIO(b"[]")
        self.assertEqual(request("/repos/a/b/issues", "secret", opener=opener,
                                 sleeper=lambda s: None), [])
        self.assertEqual(len(calls), 2)

    def test_5xx_exhaustion_fails_closed(self):
        calls = []
        def opener(req, timeout):
            calls.append(1)
            raise HTTPError(req.full_url, 503, "down", {}, None)
        with self.assertRaises(HTTPError):
            request("/repos/a/b/issues", "secret", opener=opener, sleeper=lambda s: None)
        self.assertEqual(len(calls), 4)

class IndependentDurableWorker(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dbpath = os.path.join(self.temp.name, "qa.sqlite3")
        self.db = DurableWorkStore(self.dbpath)
        self.db.ingest(work(), now=100)
    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_restart_preserves_pending(self):
        self.db.close()
        self.db = DurableWorkStore(self.dbpath)
        self.assertEqual(self.db.snapshot(123)["status"], "PENDING")

    def test_second_connection_cannot_claim_active_lease(self):
        other = DurableWorkStore(self.dbpath)
        try:
            self.assertEqual(self.db.claim("same", now=101)["attempt"], 1)
            self.assertIsNone(other.claim("other", now=102))
        finally:
            other.close()

    def test_different_owner_cannot_finish_expired_lease(self):
        self.db.claim("worker-A", now=101, lease_seconds=30)
        self.assertEqual(self.db.claim("worker-B", now=132)["attempt"], 2)
        self.assertFalse(self.db.finish(123, "worker-A", "proof from expired worker", now=133))

    def test_stale_same_owner_cannot_finish_new_lease(self):
        """FENCING: same string owner is NOT a unique lease generation token."""
        self.db.claim("worker-A", now=101, lease_seconds=30)
        self.assertEqual(self.db.claim("worker-A", now=132, lease_seconds=30)["attempt"], 2)
        # A delayed first-attempt completion must not complete second-attempt lease.
        self.assertFalse(self.db.finish(123, "worker-A", "old attempt proof must be rejected", now=133))

    def test_stale_same_owner_cannot_heartbeat_new_lease(self):
        """FENCING: stale attempt must not extend newly claimed lease."""
        self.db.claim("worker-A", now=101, lease_seconds=30)
        self.assertEqual(self.db.claim("worker-A", now=132, lease_seconds=30)["attempt"], 2)
        self.assertFalse(self.db.heartbeat(123, "worker-A", now=133, lease_seconds=300))

    def test_third_failed_attempt_blocks(self):
        for t in (101, 162, 283):
            self.assertIsNotNone(self.db.claim("worker-A", now=t))
            self.assertTrue(self.db.fail(123, "worker-A", now=t+1))
        self.assertEqual(self.db.snapshot(123)["status"], "BLOCKED")

    def test_no_actual_agent_invocation_or_ready(self):
        self.assertNotIn("agent_invoked", self.db.snapshot(123))
        self.assertNotIn("READY", self.db.snapshot(123))

if __name__ == "__main__":
    unittest.main()
