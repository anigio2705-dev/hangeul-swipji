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
            current_sha = chr(ord("a") + i) * 40
            s = advance(s, f"dev-{i}", "DEV_PASS", current_sha)
            s = advance(s, f"fail-{i}", "QA_FAIL", current_sha)
            if i < 2:
                s = advance(s, f"rework-{i}", "REWORK_STARTED", current_sha)
                s = advance(s, f"newsha-{i}", "SHA_CHANGED", current_sha,
                            new_sha=chr(ord("b") + i) * 40)
        self.assertEqual((s.phase, s.qa_failures), ("BLOCKED", 3))
        with self.assertRaises(ValueError):
            advance(s, "again", "REWORK_STARTED", s.sha)

    def test_failed_sha_must_change_before_dev_pass(self):
        s = advance(QueueState(102, A), "dev", "DEV_PASS", A)
        s = advance(s, "fail", "QA_FAIL", A)
        s = advance(s, "start", "REWORK_STARTED", A)
        with self.assertRaises(ValueError):
            advance(s, "dev-again", "DEV_PASS", A)
        s = advance(s, "new", "SHA_CHANGED", A, new_sha=B)
        s = advance(s, "dev-b", "DEV_PASS", B)
        s = advance(s, "qa-b", "QA_PASS", B)
        self.assertEqual(s.phase, "REVIEW_PENDING")

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

    def test_failed_sha_rejected_after_a_to_b_to_a(self):
        s = advance(QueueState(102, A), "dev-a", "DEV_PASS", A)
        s = advance(s, "fail-a", "QA_FAIL", A)
        s = advance(s, "rework-a", "REWORK_STARTED", A)
        s = advance(s, "a-to-b", "SHA_CHANGED", A, new_sha=B)
        self.assertEqual(s.rejected_shas, (A,))
        with self.assertRaises(ValueError):
            advance(s, "b-to-a", "SHA_CHANGED", B, new_sha=A)
        # Rejected history survives subsequent legitimate changes.
        c = "c" * 40
        s = advance(s, "b-to-c", "SHA_CHANGED", B, new_sha=c)
        with self.assertRaises(ValueError):
            advance(s, "c-to-a", "SHA_CHANGED", c, new_sha=A)

    def test_failed_b_cannot_rollback_to_a_or_b(self):
        c = "c" * 40
        s = advance(QueueState(102, A), "dev-a", "DEV_PASS", A)
        s = advance(s, "fail-a", "QA_FAIL", A)
        s = advance(s, "a-to-b", "SHA_CHANGED", A, new_sha=B)
        s = advance(s, "dev-b", "DEV_PASS", B)
        s = advance(s, "fail-b", "QA_FAIL", B)
        s = advance(s, "b-to-c", "SHA_CHANGED", B, new_sha=c)
        self.assertEqual(s.rejected_shas, (A, B))
        for candidate in (A, B):
            with self.assertRaises(ValueError):
                advance(s, "rollback-" + candidate[0], "SHA_CHANGED", c,
                        new_sha=candidate)
        s = advance(s, "dev-c", "DEV_PASS", c)
        s = advance(s, "qa-c", "QA_PASS", c)
        s = advance(s, "central-c", "CENTRAL_PASS", c)
        self.assertEqual(s.phase, "ATTESTATION_PENDING")

    def test_rejected_history_validation(self):
        with self.assertRaises(ValueError):
            QueueState(102, A, rejected_shas=(A, A))
        with self.assertRaises(ValueError):
            QueueState(102, A, rejected_shas=("invalid",))



class QA15IndependentRollbackRecheck(unittest.TestCase):
    """Independent QA-only replay of the two previously failing PR #159 cases."""

    def _failed_a_then_b(self):
        s = advance(QueueState(102, A), "qa15-dev-a", "DEV_PASS", A)
        s = advance(s, "qa15-fail-a", "QA_FAIL", A)
        self.assertEqual(s.rejected_shas, (A,))
        s = advance(s, "qa15-start-a", "REWORK_STARTED", A)
        s = advance(s, "qa15-a-to-b", "SHA_CHANGED", A, new_sha=B)
        self.assertEqual((s.sha, s.phase, s.rejected_shas), (B, "DEVELOP", (A,)))
        return s

    def test_qa15_original_fail_1_reject_a_to_b_to_a(self):
        s = self._failed_a_then_b()
        with self.assertRaisesRegex(ValueError, "Previously QA-rejected SHA"):
            advance(s, "qa15-b-to-a", "SHA_CHANGED", B, new_sha=A)
        self.assertEqual((s.sha, s.phase, s.rejected_shas), (B, "DEVELOP", (A,)))

    def test_qa15_original_fail_2_never_attest_rejected_a(self):
        s = self._failed_a_then_b()
        with self.assertRaises(ValueError):
            s = advance(s, "qa15-rollback-a", "SHA_CHANGED", B, new_sha=A)
            s = advance(s, "qa15-dev-rejected-a", "DEV_PASS", A)
            s = advance(s, "qa15-qa-rejected-a", "QA_PASS", A)
            s = advance(s, "qa15-central-rejected-a", "CENTRAL_PASS", A)
        self.assertNotEqual(s.phase, "ATTESTATION_PENDING")

    def test_qa15_valid_b_requires_fresh_dev_qa_central(self):
        s = self._failed_a_then_b()
        with self.assertRaises(ValueError):
            advance(s, "qa15-old-qa", "QA_PASS", A)
        s = advance(s, "qa15-dev-b", "DEV_PASS", B)
        s = advance(s, "qa15-qa-b", "QA_PASS", B)
        s = advance(s, "qa15-central-b", "CENTRAL_PASS", B)
        self.assertEqual((s.sha, s.phase, s.rejected_shas),
                         (B, "ATTESTATION_PENDING", (A,)))

    def test_qa15_second_failure_retains_all_rejections(self):
        s = self._failed_a_then_b()
        s = advance(s, "qa15-dev-b", "DEV_PASS", B)
        s = advance(s, "qa15-fail-b", "QA_FAIL", B)
        self.assertEqual(s.rejected_shas, (A, B))
        c = "c" * 40
        s = advance(s, "qa15-b-to-c", "SHA_CHANGED", B, new_sha=c)
        for old in (A, B):
            with self.assertRaisesRegex(ValueError, "Previously QA-rejected SHA"):
                advance(s, "qa15-revert-" + old[0], "SHA_CHANGED", c, new_sha=old)

    def test_qa15_duplicate_failure_idempotent_and_rejected_once(self):
        s = advance(QueueState(102, A), "qa15-dev-a", "DEV_PASS", A)
        s = advance(s, "qa15-fail-a", "QA_FAIL", A)
        self.assertEqual(advance(s, "qa15-fail-a", "QA_FAIL", A), s)
        self.assertEqual((s.qa_failures, s.rejected_shas), (1, (A,)))

if __name__ == "__main__":
    unittest.main()
