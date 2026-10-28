"""Read-only review workflow prompt safety, no API key or external call."""
import unittest
from hq_workstyle_review import ROLES, messages, evidence
class ReviewTests(unittest.TestCase):
    def test_four_roles_have_separate_context(self):
        self.assertEqual(len(ROLES),4)
        prompts=[messages(role)[1]["content"] for role in ROLES]
        self.assertEqual(len(set(prompts)),4)
        self.assertTrue(all("same_evidence" in p for p in prompts))
    def test_evidence_does_not_claim_green_ci_is_complete(self):
        self.assertEqual(evidence()["final_completed"],0)
        self.assertIn("No controlled",evidence()["comparison_limits"])
    def test_unknown_role_is_rejected(self):
        with self.assertRaises(ValueError):messages("not-a-role")
if __name__=="__main__":unittest.main()
