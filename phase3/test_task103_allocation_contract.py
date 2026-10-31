"""#103 isolated arithmetic contracts; no payments, policy approval, or DB writes."""
import unittest

from team14_persistent import SimError
from team14_referral_eligibility import eligible_referral
from team14_referral_scenarios import simulate_referral


class Task103AllocationTests(unittest.TestCase):
    def assert_budget(self, result):
        self.assertEqual(
            result["gross_krw"],
            result["teacher_krw"]
            + result["platform_krw"]
            + sum(r["amount_krw"] for r in result["recipients"]),
        )
        self.assertFalse(result["real_money"])
        self.assertFalse(result["policy_approved"])
        self.assertFalse(result["payment_enabled"])

    def test_direct_100000(self):
        x = eligible_referral(100000, "student", [("student", "alice")], (300,), 2000)
        self.assertEqual((x["teacher_krw"], x["platform_krw"]), (77000, 20000))
        self.assertEqual(x["recipients"], [{"user_id": "alice", "amount_krw": 3000}])
        self.assert_budget(x)

    def test_two_ancestors_100000(self):
        x = eligible_referral(
            100000, "student",
            [("student", "alice"), ("alice", "bob")], (300, 100), 2000
        )
        self.assertEqual((x["teacher_krw"], x["platform_krw"]), (76000, 20000))
        self.assertEqual(x["recipients"], [
            {"user_id": "alice", "amount_krw": 3000},
            {"user_id": "bob", "amount_krw": 1000},
        ])
        self.assert_budget(x)

    def test_missing_second_ancestor_is_not_paid(self):
        x = eligible_referral(
            100000, "student", [("student", "alice")], (300, 100), 2000
        )
        self.assertEqual((x["teacher_krw"], x["platform_krw"]), (76000, 21000))
        self.assertEqual(x["recipients"], [{"user_id": "alice", "amount_krw": 3000}])
        self.assert_budget(x)

    def test_no_ancestors_retains_unallocated_share(self):
        x = eligible_referral(100000, "student", [], (300, 100), 2000)
        self.assertEqual((x["teacher_krw"], x["platform_krw"]), (76000, 24000))
        self.assertEqual(x["recipients"], [])
        self.assert_budget(x)

    def test_small_amount_rounding_conserves_gross(self):
        x = eligible_referral(
            101, "student",
            [("student", "alice"), ("alice", "bob")], (333, 167), 2000
        )
        self.assertEqual((x["teacher_krw"], x["platform_krw"]), (75, 22))
        self.assertEqual([r["amount_krw"] for r in x["recipients"]], [3, 1])
        self.assert_budget(x)

    def test_abstract_simulator_does_not_filter_missing_ancestors(self):
        edges = [("student", "alice")]
        abstract = simulate_referral(100000, edges, (300, 100), 2000)
        eligible = eligible_referral(100000, "student", edges, (300, 100), 2000)
        self.assertEqual((abstract["teacher"], abstract["platform"], abstract["rewards"]),
                         (76000, 20000, [3000, 1000]))
        self.assertEqual((eligible["teacher_krw"], eligible["platform_krw"]),
                         (76000, 21000))
        self.assertEqual(len(eligible["recipients"]), 1)
        self.assertFalse(abstract["payment_enabled"])

    def test_over_budget_rejected(self):
        with self.assertRaises(SimError):
            eligible_referral(100000, "student", [], (9000, 2000), 2000)


if __name__ == "__main__":
    unittest.main()
