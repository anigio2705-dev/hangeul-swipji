"""Independent #101 mock referral graph capacity regression.

The graph is test-only. These checks never write real referrals or grant money.
"""
import unittest

from team14_persistent import SimError
from team14_referral_scenarios import simulate_introduction_review


class ReferralCapacityBoundaryTests(unittest.TestCase):
    def review(self, decision, edges):
        return simulate_introduction_review(
            "alice", "teacher", "bob", "student", decision,
            existing_edges=edges,
        )

    def test_accepted_proposal_cannot_exceed_ten_thousand_edges(self):
        existing = [("alice", "child" + str(i)) for i in range(10000)]
        with self.assertRaises(SimError) as context:
            self.review("accept", existing)
        self.assertEqual(context.exception.code, "VALIDATION_ERROR")

    def test_one_remaining_slot_accepts_mock_only(self):
        existing = [("alice", "child" + str(i)) for i in range(9999)]
        result = self.review("accept", existing)
        self.assertEqual(result["review_decision"], "accept")
        for key in ("real_money", "payment_enabled", "policy_approved",
                    "identity_verified", "authorization_granted",
                    "reward_eligible"):
            self.assertIs(result[key], False)

    def test_full_graph_can_still_reject_without_new_edge(self):
        existing = [("alice", "child" + str(i)) for i in range(10000)]
        result = self.review("reject", existing)
        self.assertEqual(result["review_decision"], "reject")
        self.assertIs(result["authorization_granted"], False)
        self.assertIs(result["payment_enabled"], False)


if __name__ == "__main__":
    unittest.main()
