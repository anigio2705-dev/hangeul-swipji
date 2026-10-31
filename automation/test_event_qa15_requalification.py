"""QA15-only negative cases for PR #157 exact central HEAD bd68376c.

Do not merge as product code. This deliberately challenges whether a previously
rejected SHA can be laundered through a different SHA and reintroduced.
"""
import unittest
from event_work_queue import QueueState, advance

A = "a" * 40
B = "b" * 40


class QA15RequalificationNegative(unittest.TestCase):
    def rejected_a(self):
        s = advance(QueueState(102, A), "dev-a", "DEV_PASS", A)
        s = advance(s, "fail-a", "QA_FAIL", A)
        self.assertEqual(s.phase, "REWORK")
        return advance(s, "rework-a", "REWORK_STARTED", A)

    def test_qa15_same_sha_dev_pass_still_rejected(self):
        s = self.rejected_a()
        with self.assertRaises(ValueError):
            advance(s, "dev-a-repeat", "DEV_PASS", A)

    def test_qa15_rejected_sha_cannot_be_restored_via_intermediate_sha(self):
        s = self.rejected_a()
        s = advance(s, "sha-a-to-b", "SHA_CHANGED", A, new_sha=B)
        # A was rejected by independent QA; switching B back to A must
        # not make that failed candidate eligible again.
        with self.assertRaises(ValueError):
            advance(s, "sha-b-to-a", "SHA_CHANGED", B, new_sha=A)

    def test_qa15_rejected_sha_cannot_attest_after_rollback(self):
        s = self.rejected_a()
        s = advance(s, "sha-a-to-b", "SHA_CHANGED", A, new_sha=B)
        # A->B->A is currently syntactically possible. A previous QA_FAIL
        # must not be erased by this rollback.
        try:
            s = advance(s, "sha-b-to-a", "SHA_CHANGED", B, new_sha=A)
        except ValueError:
            return
        s = advance(s, "dev-a-again", "DEV_PASS", A)
        s = advance(s, "qa-a-again", "QA_PASS", A)
        s = advance(s, "central-a-again", "CENTRAL_PASS", A)
        self.assertNotEqual(
            s.phase, "ATTESTATION_PENDING",
            "QA_FAIL(A) bypassed by SHA_CHANGED(A->B->A) with no fix")

    def test_qa15_genuine_new_sha_requires_fresh_qa_and_central(self):
        s = self.rejected_a()
        s = advance(s, "sha-a-to-b", "SHA_CHANGED", A, new_sha=B)
        with self.assertRaises(ValueError):
            advance(s, "stale-qa-a", "QA_PASS", A)
        s = advance(s, "dev-b", "DEV_PASS", B)
        s = advance(s, "qa-b", "QA_PASS", B)
        s = advance(s, "central-b", "CENTRAL_PASS", B)
        self.assertEqual(s.phase, "ATTESTATION_PENDING")

    def test_qa15_duplicate_fail_id_does_not_exhaust_retries(self):
        s = self.rejected_a()
        self.assertEqual(s.qa_failures, 1)
        self.assertEqual(advance(s, "fail-a", "QA_FAIL", A), s)


if __name__ == "__main__":
    unittest.main()
