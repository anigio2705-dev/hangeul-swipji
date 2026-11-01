"""Deterministic negative/positive tests for the event-state contract."""
import unittest
from event_ready_state import Evidence, decide

SHA1 = "a" * 40
SHA2 = "b" * 40


def ev(role, outcome="OK", sha=SHA1, principal=None, run_id=None):
    return Evidence(102, sha, role, principal or role, run_id or ("run-" + role), outcome)


class EventReadyStateTest(unittest.TestCase):
    def test_empty_is_not_ready(self):
        self.assertEqual(decide(102, SHA1, []), "DEVELOPMENT_PENDING")

    def test_developer_requests_qa(self):
        self.assertEqual(decide(102, SHA1, [ev("developer")]), "QA_REQUESTED")

    def test_qa_fail_requires_rework(self):
        self.assertEqual(decide(102, SHA1, [ev("developer"), ev("qa15", "QA_FAIL")]),
                         "QA_FAIL_REWORK_REQUIRED")

    def test_new_sha_does_not_inherit_old_qa(self):
        events = [ev("developer"), ev("qa15"), ev("central"), ev("developer", sha=SHA2)]
        self.assertEqual(decide(102, SHA2, events), "QA_REQUESTED")

    def test_same_principal_cannot_vote_twice(self):
        events = [ev("developer", principal="same"), ev("qa15", principal="same"),
                  ev("central", principal="central")]
        self.assertEqual(decide(102, SHA1, events), "APPROVAL_PENDING_SAME_PRINCIPAL")

    def test_same_run_cannot_vote_twice(self):
        events = [ev("developer", run_id="same"), ev("qa15", run_id="same"), ev("central")]
        self.assertEqual(decide(102, SHA1, events), "APPROVAL_PENDING_SAME_RUN")

    def test_missing_central_cannot_approve(self):
        self.assertEqual(decide(102, SHA1, [ev("developer"), ev("qa15")]),
                         "APPROVAL_PENDING_CENTRAL")

    def test_three_roles_still_not_ready_without_attestation(self):
        self.assertEqual(decide(102, SHA1, [ev("developer"), ev("qa15"), ev("central")]),
                         "THREE_ROLE_EVIDENCE_PRESENT_UNATTESTED")

    def test_identical_duplicate_is_idempotent(self):
        e = ev("developer")
        self.assertEqual(decide(102, SHA1, [e, e]), "QA_REQUESTED")

    def test_conflicting_duplicate_rejected(self):
        e = ev("developer")
        conflicting = ev("developer", outcome="IN_PROGRESS")
        with self.assertRaises(ValueError):
            decide(102, SHA1, [e, conflicting])

    def test_invalid_sha_rejected(self):
        with self.assertRaises(ValueError):
            decide(102, "not-a-sha", [])


if __name__ == "__main__":
    unittest.main()
