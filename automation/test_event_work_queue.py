"""Negative and positive deterministic queue-transition tests."""
import unittest
from event_work_queue import QueueState, advance

A = "a" * 40
B = "b" * 40


class EventQueueTest(unittest.TestCase):
    def test_normal_path_never_auto_ready(self):
        s = QueueState(102, A)
        for i, action in enumerate(("DEV_PASS", "QA_PASS", "CENTRAL_PASS")):
            s = advance(s, f"event-{i}", action, A)
        self.assertEqual(s.phase, "ATTESTATION_PENDING")

    def test_duplicate_delivery_idempotent(self):
        s = QueueState(102, A)
        next_state = advance(s, "evt1", "DEV_PASS", A)
        self.assertEqual(advance(next_state, "evt1", "DEV_PASS", A), next_state)

    def test_conflicting_duplicate_rejected(self):
        s = advance(QueueState(102, A), "evt1", "DEV_PASS", A)
        with self.assertRaises(ValueError):
            advance(s, "evt1", "QA_PASS", A)

    def test_out_of_order_qa_rejected(self):
        with self.assertRaises(ValueError):
            advance(QueueState(102, A), "evt", "QA_PASS", A)

    def test_qa_fail_rework_and_new_sha(self):
        s = advance(QueueState(102, A), "dev", "DEV_PASS", A)
        s = advance(s, "fail", "QA_FAIL", A)
        self.assertEqual((s.phase, s.qa_failures), ("REWORK", 1))
        s = advance(s, "rework", "REWORK_STARTED", A)
        s = advance(s, "sha", "SHA_CHANGED", A, new_sha=B)
        self.assertEqual((s.phase, s.sha), ("DEVELOP", B))
        with self.assertRaises(ValueError):
            advance(s, "old-qa", "QA_PASS", A)

    def test_late_qa_failure_revokes_qa_pass(self):
        s = QueueState(102, A)
        s = advance(s, "dev", "DEV_PASS", A)
        s = advance(s, "qa-pass", "QA_PASS", A)
        self.assertEqual(s.phase, "REVIEW_PENDING")
        s = advance(s, "late-fail", "QA_FAIL", A)
        self.assertEqual((s.phase, s.qa_failures), ("REWORK", 1))
        with self.assertRaises(ValueError):
            advance(s, "central-should-not-pass", "CENTRAL_PASS", A)

    def test_late_qa_failure_revokes_central_attestation(self):
        s = QueueState(102, A)
        for event_id, action in (
            ("dev", "DEV_PASS"),
            ("qa-pass", "QA_PASS"),
            ("central", "CENTRAL_PASS"),
        ):
            s = advance(s, event_id, action, A)
        self.assertEqual(s.phase, "ATTESTATION_PENDING")
        s = advance(s, "late-fail", "QA_FAIL", A)
        self.assertEqual((s.phase, s.qa_failures), ("REWORK", 1))
        with self.assertRaises(ValueError):
            advance(s, "another-central", "CENTRAL_PASS", A)

    def test_duplicate_late_failure_does_not_double_count(self):
        s = QueueState(102, A)
        s = advance(s, "dev", "DEV_PASS", A)
        s = advance(s, "qa", "QA_PASS", A)
        s = advance(s, "fail", "QA_FAIL", A)
        self.assertEqual(advance(s, "fail", "QA_FAIL", A), s)
        self.assertEqual(s.qa_failures, 1)

    def test_max_retry_cap_blocks(self):
        s = QueueState(102, A)
        for i in range(3):
            s = advance(s, f"dev-{i}", "DEV_PASS", A)
            s = advance(s, f"fail-{i}", "QA_FAIL", A)
            if i < 2:
                s = advance(s, f"rework-{i}", "REWORK_STARTED", A)
        self.assertEqual((s.phase, s.qa_failures), ("BLOCKED", 3))
        with self.assertRaises(ValueError):
            advance(s, "again", "REWORK_STARTED", A)

    def test_sha_change_invalidates_prior_qa(self):
        s = QueueState(102, A)
        s = advance(s, "dev", "DEV_PASS", A)
        s = advance(s, "qa", "QA_PASS", A)
        s = advance(s, "change", "SHA_CHANGED", A, new_sha=B)
        self.assertEqual(s.phase, "DEVELOP")

    def test_invalid_sha_and_event(self):
        with self.assertRaises(ValueError):
            QueueState(102, "short")
        with self.assertRaises(ValueError):
            advance(QueueState(102, A), "", "DEV_PASS", A)

    def test_no_untrusted_ready_action(self):
        with self.assertRaises(ValueError):
            advance(QueueState(102, A), "force", "READY", A)


if __name__ == "__main__":
    unittest.main()
