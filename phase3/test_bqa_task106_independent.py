"""B/15 independent QA-only #106; product SHA 9493f60b38585ec58c6ea05781015d5e70bd73b8."""
import itertools
import unittest

from team14_incentive_stacking_sim import simulate_incentive_options


def sim(**changes):
    args = dict(policy="all_candidates", gross_krw=10000,
                discount_request_krw=3000, points_request_krw=3000,
                cash_request_krw=3000, age_days=0, cap_krw=5000)
    args.update(changes)
    return simulate_incentive_options(**args)


class BIndependentTask106Tests(unittest.TestCase):
    def assert_safe(self, value):
        for field in ("real_money", "payment_enabled", "points_credited",
                      "cash_payout_enabled", "policy_approved"):
            self.assertIs(value[field], False)
        self.assertGreaterEqual(value["unused_hypothetical_cap_krw"], 0)
        self.assertLessEqual(value["combined_candidate_krw"],
                             value["hypothetical_cap_krw"])
        self.assertEqual(value["hypothetical_cap_krw"],
                         value["combined_candidate_krw"] +
                         value["unused_hypothetical_cap_krw"])

    def test_exhaustive_policy_age_and_cap_safety_matrix(self):
        for policy, age, cap in itertools.product(
            ("discount_only", "discount_plus_points", "all_candidates"),
            (0, 30, 31, 90, 91), (0, 1, 1000, 5000, 10000, 50000)
        ):
            with self.subTest(policy=policy, age=age, cap=cap):
                value = sim(policy=policy, age_days=age, cap_krw=cap)
                self.assert_safe(value)

    def test_priority_discount_then_points_then_cash_under_tiny_cap(self):
        a = sim(cap_krw=1)
        self.assertEqual((1, 0, 0), (a["discount_candidate_krw"],
                                    a["points_candidate_krw"],
                                    a["cash_equivalent_candidate_krw"]))
        b = sim(age_days=31, cap_krw=1)
        self.assertEqual((0, 1, 0), (b["discount_candidate_krw"],
                                    b["points_candidate_krw"],
                                    b["cash_equivalent_candidate_krw"]))
        self.assert_safe(a)
        self.assert_safe(b)

    def test_expiration_exactly_30_31_90_91(self):
        self.assertGreater(sim(age_days=30)["discount_candidate_krw"], 0)
        self.assertEqual(0, sim(age_days=31)["discount_candidate_krw"])
        self.assertGreater(sim(age_days=90)["points_candidate_krw"], 0)
        self.assertEqual(0, sim(age_days=91)["points_candidate_krw"])
        self.assertEqual(0, sim(age_days=91)["cash_equivalent_candidate_krw"])

    def test_exclusive_policy_does_not_grant_other_candidates(self):
        only = sim(policy="discount_only")
        self.assertEqual(0, only["points_candidate_krw"])
        self.assertEqual(0, only["cash_equivalent_candidate_krw"])
        both = sim(policy="discount_plus_points")
        self.assertEqual(0, both["cash_equivalent_candidate_krw"])
        self.assert_safe(only)
        self.assert_safe(both)

    def test_zero_gross_and_gross_less_than_cap(self):
        for gross, cap in ((0, 1000), (1, 10000), (5, 9999)):
            value = sim(gross_krw=gross, cap_krw=cap)
            self.assertEqual(gross, value["hypothetical_cap_krw"])
            self.assertGreaterEqual(value["hypothetical_payable_after_discount_krw"], 0)
            self.assert_safe(value)

    def test_untrusted_truthy_and_fractional_amounts_rejected(self):
        for field in ("gross_krw", "discount_request_krw", "points_request_krw",
                      "cash_request_krw", "age_days", "cap_krw"):
            for bad in (True, False, 1.1, "100", -1, 10**9 + 1, None):
                with self.subTest(field=field, bad=repr(bad)):
                    with self.assertRaises(ValueError):
                        sim(**{field: bad})

    def test_unknown_policy_cannot_activate_payment(self):
        for policy in ("live", "cash_payout", None, 1, {}, ""):
            with self.subTest(policy=repr(policy)), self.assertRaises(ValueError):
                sim(policy=policy)

    def test_maximum_bounded_requests_never_over_allocate(self):
        for policy in ("discount_only", "discount_plus_points", "all_candidates"):
            value = sim(policy=policy, gross_krw=10**9,
                        discount_request_krw=10**9, points_request_krw=10**9,
                        cash_request_krw=10**9, cap_krw=10**9)
            self.assertEqual(10**9, value["combined_candidate_krw"])
            self.assert_safe(value)


if __name__ == "__main__":
    unittest.main()
