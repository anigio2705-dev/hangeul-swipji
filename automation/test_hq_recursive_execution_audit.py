"""Adversarial tests: do not promote role definitions or synthetic IDs."""
import unittest
from hq_recursive_execution_audit import assess

RUN = "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/40829945192"
SHA = "a" * 40


def event(role, call, task=11, **kw):
    return {"team": "11", "role": role, "call_id": call, "task_number": task, **kw}


class RecursiveAuditTests(unittest.TestCase):
    def test_no_events_never_proves_agents(self):
        self.assertEqual(assess({})["teams"]["11"]["status"], "NOT_PROVEN")

    def test_unverified_claims_never_count_as_calls(self):
        claims = [event("implementation", "claim-1", commit_sha=SHA, changed_files=["x.py"])]
        self.assertEqual(assess({"events": claims})["teams"]["11"]["status"], "UNVERIFIED")

    def test_duplicate_call_ids_rejected(self):
        data = {"events": [event("discovery", "same"), event("qa", "same")]}
        result = assess(data, ["same"])
        self.assertTrue(result["invalid_events"])
        self.assertEqual(result["teams"]["11"]["independently_verified_calls"], 1)

    def test_cross_team_task_claim_rejected(self):
        result = assess({"events": [event("discovery", "x", task=47)]}, ["x"])
        self.assertIn("does not own", result["invalid_events"][0])

    def test_qa_same_call_as_implementation_never_proves_independence(self):
        result = assess({"events": [event("implementation", "one", commit_sha=SHA, changed_files=["x.py"])]}, ["one"])
        self.assertFalse(result["teams"]["11"]["independent_qa_pair"])

    def test_independent_reviewable_not_final_approval(self):
        data = {"events": [
            event("discovery", "d"),
            event("implementation", "i", commit_sha=SHA, changed_files=["x.py"]),
            event("qa", "q", ci_result="success", ci_url=RUN),
            event("queue", "n", next_task_number=12),
        ]}
        result = assess(data, ["d", "i", "q", "n"])
        self.assertEqual(result["teams"]["11"]["status"], "REVIEW_REQUIRED")
        self.assertFalse(result["owner_approved"])

    def test_failed_execution_needs_distinct_repair(self):
        data = {"events": [
            event("discovery", "d"),
            event("implementation", "i", commit_sha=SHA, changed_files=["x.py"], outcome="failed"),
            event("qa", "q", ci_result="success", ci_url=RUN),
            event("queue", "n", next_task_number=12),
        ]}
        self.assertEqual(assess(data, ["d", "i", "q", "n"])["teams"]["11"]["status"], "INCOMPLETE")
        data["events"].append(event("repair", "r"))
        self.assertEqual(assess(data, ["d", "i", "q", "n", "r"])["teams"]["11"]["status"], "REVIEW_REQUIRED")

    def test_fake_ci_url_not_accepted(self):
        data = {"events": [event("qa", "q", ci_result="success", ci_url="https://example.com/fake")]}
        self.assertFalse(assess(data, ["q"])["teams"]["11"]["independent_qa_pair"])


if __name__ == "__main__":
    unittest.main()
