"""QA15 independent #103 negative contracts against central exact SHA 8c4af97e...
QA-only tests. No DB, network, payment, deployment, or policy mutation.
"""
import unittest

from team14_persistent import SimError
from team14_referral_eligibility import eligible_referral
from team14_referral_scenarios import simulate_referral


class QA15Task103NegativeTests(unittest.TestCase):
    def assert_conserved(self, x):
        self.assertEqual(x["gross_krw"], x["teacher_krw"] + x["platform_krw"] +
                         sum(p["amount_krw"] for p in x["recipients"]))
        self.assertGreaterEqual(x["teacher_krw"], 0)
        self.assertGreaterEqual(x["platform_krw"], 0)
        self.assertTrue(all(p["amount_krw"] >= 0 for p in x["recipients"]))
        for key in ("real_money", "policy_approved", "payment_enabled"):
            self.assertIs(x[key], False)

    def test_qa15_gross_rejects_zero_negative_boolean_and_over_max(self):
        for gross in (0, -1, True, 10**15 + 1, 1.5, "1000"):
            with self.subTest(gross=gross), self.assertRaises(SimError):
                eligible_referral(gross, "student", [], (300, 100), 2000)

    def test_qa15_invalid_commission_and_rates_fail_closed(self):
        cases = ((True, (300,)), (-1, (300,)), (10001, ()), (2000, (True,)),
                 (2000, (-1,)), (2000, (10001,)), (9000, (1001,)))
        for commission, rates in cases:
            with self.subTest(commission=commission, rates=rates), self.assertRaises(SimError):
                eligible_referral(100000, "student", [], rates, commission)

    def test_qa15_ten_depth_limit_and_eleven_rejected(self):
        edges = [("student" if i == 0 else "p" + str(i), "p" + str(i + 1))
                 for i in range(10)]
        result = eligible_referral(100000, "student", edges, (100,) * 10, 2000)
        self.assertEqual(len(result["recipients"]), 10)
        self.assert_conserved(result)
        with self.assertRaises(SimError):
            eligible_referral(100000, "student", edges, (100,) * 11, 2000)

    def test_qa15_unrelated_cycle_is_rejected(self):
        edges = [("student", "alice"), ("x", "y"), ("y", "x")]
        with self.assertRaises(SimError):
            eligible_referral(100000, "student", edges, (300, 100), 2000)

    def test_qa15_self_referral_duplicate_child_and_bad_id(self):
        for edges in ([("student", "student")],
                      [("student", "a"), ("student", "b")],
                      [("student", "bad user id")]):
            with self.subTest(edges=edges), self.assertRaises(SimError):
                eligible_referral(100000, "student", edges, (300, 100), 2000)

    def test_qa15_conservation_for_small_and_boundary_amounts(self):
        edges_cases = ([], [("student", "alice")],
                       [("student", "alice"), ("alice", "bob")])
        for gross in (1, 2, 3, 99, 101, 10000, 100000, 10**15):
            for edges in edges_cases:
                with self.subTest(gross=gross, edges=edges):
                    x = eligible_referral(gross, "student", edges, (333, 167), 2000)
                    self.assert_conserved(x)
                    self.assertEqual(len(x["recipients"]), len(edges))

    def test_qa15_missing_ancestor_does_not_receive_funds(self):
        x = eligible_referral(100000, "student", [("student", "alice")],
                              (300, 100), 2000)
        self.assertEqual(x["recipients"], [{"user_id": "alice", "amount_krw": 3000}])
        self.assertEqual((x["teacher_krw"], x["platform_krw"]), (76000, 21000))
        self.assert_conserved(x)

    def test_qa15_abstract_budget_is_not_an_actual_payout(self):
        edges = [("student", "alice")]
        x = simulate_referral(100000, edges, (300, 100), 2000)
        y = eligible_referral(100000, "student", edges, (300, 100), 2000)
        self.assertEqual(x["rewards"], [3000, 1000])
        self.assertEqual([p["amount_krw"] for p in y["recipients"]], [3000])
        self.assertEqual((x["platform"], y["platform_krw"]), (20000, 21000))
        for key in ("real_money", "policy_approved", "payment_enabled"):
            self.assertIs(x[key], False)
            self.assertIs(y[key], False)

    def test_qa15_zero_rates_do_not_create_negative_balances(self):
        x = eligible_referral(101, "student", [("student", "alice")], (0,), 0)
        self.assertEqual((x["teacher_krw"], x["platform_krw"]), (101, 0))
        self.assert_conserved(x)

    def test_qa15_original_103_examples(self):
        cases = (
            ([( "student", "alice")], (300,), (77000, 20000)),
            ([( "student", "alice"), ("alice", "bob")], (300, 100), (76000, 20000)),
            ([], (300, 100), (76000, 24000)),
        )
        for edges, rates, expected in cases:
            x = eligible_referral(100000, "student", edges, rates, 2000)
            self.assertEqual((x["teacher_krw"], x["platform_krw"]), expected)
            self.assert_conserved(x)


if __name__ == "__main__":
    unittest.main()
