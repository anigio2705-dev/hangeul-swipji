import tempfile
import sys
import time
import threading
import unittest
from pathlib import Path

from push_broker_authority import BrokerAuthority, BrokerDenied
from push_broker_supervisor import PushRevoked, PushUncertain, supervise_reserved

SHA = "a" * 40
BRANCH = "work/broker-safe"


class BrokerAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "broker.sqlite")
        self.now = [1000.0]
        self.broker = BrokerAuthority(self.path, clock=lambda: self.now[0])

    def tearDown(self):
        self.broker.close()
        self.tmp.cleanup()

    def lease(self, task="task-1"):
        return self.broker.issue(task, SHA, BRANCH, ttl=60)

    def test_one_shot_verified_exact_sha(self):
        token = self.lease()
        self.assertTrue(self.broker.reserve("task-1", token, SHA, BRANCH))
        self.assertTrue(self.broker.live("task-1", token, SHA, BRANCH))
        with self.assertRaises(BrokerDenied):
            self.broker.reserve("task-1", token, SHA, BRANCH)
        with self.assertRaises(BrokerDenied):
            self.broker.mark_verified("task-1", token, SHA, BRANCH, "b" * 40)
        self.assertTrue(self.broker.mark_verified("task-1", token, SHA, BRANCH, SHA))
        self.assertEqual(self.broker.state("task-1"), "VERIFIED")
        with self.assertRaises(BrokerDenied):
            self.broker.issue("task-1", SHA, BRANCH)

    def test_revocation_before_reserve(self):
        token = self.lease()
        self.assertEqual(self.broker.revoke("task-1"), "REVOKED")
        with self.assertRaises(BrokerDenied):
            self.broker.reserve("task-1", token, SHA, BRANCH)
        self.assertFalse(self.broker.live("task-1", token, SHA, BRANCH))

    def test_in_flight_revocation_is_uncertain_never_success(self):
        token = self.lease()
        self.broker.reserve("task-1", token, SHA, BRANCH)
        self.assertEqual(self.broker.revoke("task-1"), "PUSH_UNCERTAIN")
        with self.assertRaises(BrokerDenied):
            self.broker.mark_verified("task-1", token, SHA, BRANCH, SHA)
        self.assertFalse(self.broker.live("task-1", token, SHA, BRANCH))
        self.assertEqual(self.broker.revoke("task-1"), "PUSH_UNCERTAIN")

    def test_restart_quarantines_possible_orphan(self):
        token = self.lease()
        self.broker.reserve("task-1", token, SHA, BRANCH)
        self.broker.close()
        self.broker = BrokerAuthority(self.path, clock=lambda: self.now[0])
        self.assertEqual(self.broker.recover(), {"uncertain": 1, "expired": 0})
        self.assertEqual(self.broker.state("task-1"), "PUSH_UNCERTAIN")
        with self.assertRaises(BrokerDenied):
            self.broker.reserve("task-1", token, SHA, BRANCH)

    def test_expiry_before_and_after_reservation(self):
        token = self.lease()
        self.now[0] += 61
        with self.assertRaises(BrokerDenied):
            self.broker.reserve("task-1", token, SHA, BRANCH)
        self.assertEqual(self.broker.recover()["expired"], 1)
        self.assertEqual(self.broker.state("task-1"), "REVOKED")
        token2 = self.lease("task-2")
        self.broker.reserve("task-2", token2, SHA, BRANCH)
        self.now[0] += 61
        self.assertFalse(self.broker.live("task-2", token2, SHA, BRANCH))
        with self.assertRaises(BrokerDenied):
            self.broker.mark_verified("task-2", token2, SHA, BRANCH, SHA)

    def test_reject_invalid_and_cross_sha(self):
        for branch in ("main", "work/../escape", "work//bad", "work/end/"):
            with self.assertRaises(BrokerDenied):
                self.broker.issue("task-bad", SHA, branch)
        for sha in ("abc", "b" * 39, "A" * 40):
            with self.assertRaises(BrokerDenied):
                self.broker.issue("task-bad", sha, BRANCH)
        token = self.lease()
        for args in (("bad-token", SHA, BRANCH),
                     (token, "b" * 40, BRANCH),
                     (token, SHA, "work/other")):
            with self.assertRaises(BrokerDenied):
                self.broker.reserve("task-1", *args)
        self.assertEqual(self.broker.state("task-1"), "ACTIVE")

    def test_concurrent_claim_exactly_one_winner(self):
        token = self.lease()
        barrier = threading.Barrier(2)
        results = []
        def contender():
            other = BrokerAuthority(self.path, clock=lambda: self.now[0])
            try:
                barrier.wait(timeout=3)
                try:
                    other.reserve("task-1", token, SHA, BRANCH)
                    results.append("won")
                except BrokerDenied:
                    results.append("denied")
            finally:
                other.close()
        threads = [threading.Thread(target=contender) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        self.assertEqual(sorted(results), ["denied", "won"])

    def test_recovery_idempotent_and_no_network(self):
        token = self.lease()
        self.assertEqual(self.broker.recover(), {"uncertain": 0, "expired": 0})
        self.broker.reserve("task-1", token, SHA, BRANCH)
        self.assertEqual(self.broker.recover(), {"uncertain": 1, "expired": 0})
        self.assertEqual(self.broker.recover(), {"uncertain": 0, "expired": 0})

    def test_reserved_fake_transport_needs_separate_remote_proof(self):
        token = self.lease()
        result = supervise_reserved(
            [sys.executable, "-c", "print('fake-only')"],
            authority=self.broker, task="task-1", token=token,
            sha=SHA, branch=BRANCH, timeout=2)
        self.assertEqual(result.stdout.strip(), "fake-only")
        self.assertEqual(self.broker.state("task-1"), "PUSH_IN_FLIGHT")
        self.assertTrue(self.broker.mark_verified("task-1", token, SHA, BRANCH, SHA))

    def test_reserved_failed_transport_quarantined(self):
        token = self.lease()
        with self.assertRaises(PushUncertain):
            supervise_reserved(
                [sys.executable, "-c", "import sys;sys.exit(3)"],
                authority=self.broker, task="task-1", token=token,
                sha=SHA, branch=BRANCH, timeout=2)
        self.assertEqual(self.broker.state("task-1"), "PUSH_UNCERTAIN")

    def test_reserved_revoked_during_fake_transport(self):
        token = self.lease()
        def cancel():
            time.sleep(0.15)
            other = BrokerAuthority(self.path, clock=lambda: self.now[0])
            try:
                other.revoke("task-1")
            finally:
                other.close()
        t = threading.Thread(target=cancel)
        t.start()
        try:
            with self.assertRaises((PushRevoked, PushUncertain)):
                supervise_reserved(
                    [sys.executable, "-c", "import time;time.sleep(1)"],
                    authority=self.broker, task="task-1", token=token,
                    sha=SHA, branch=BRANCH, timeout=2, interval=0.03)
        finally:
            t.join(timeout=3)
        self.assertEqual(self.broker.state("task-1"), "PUSH_UNCERTAIN")


if __name__ == "__main__":
    unittest.main()
