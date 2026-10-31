"""#106 hypothetical incentive stacking negative and boundary cases."""
import unittest

from team14_incentive_stacking_sim import simulate_incentive_options as sim


def sample(**overrides):
    kwargs = dict(
        policy="all_candidates", gross_krw=10000,
        discount_request_krw=2000, points_request_krw=1000,
        cash_request_krw=500, age_days=0, cap_krw=4000,
    )
    kwargs.update(overrides)
    return sim(**kwargs)


class IncentiveStackingTests(unittest.TestCase):
    def assert_no_live_effects(self, value):
        for key in ("real_money", "payment_enabled", "points_credited",
                    "cash_payout_enabled", "policy_approved"):
            self.assertIs(value[key], False, key)

    def test_all_candidates_within_cap(self):
        value = sample()
        self.assertEqual(value["discount_candidate_krw"], 2000)
        self.assertEqual(value["points_candidate_krw"], 1000)
        self.assertEqual(value["cash_equivalent_candidate_krw"], 500)
        self.assertEqual(value["combined_candidate_krw"], 3500)
        self.assertEqual(value["unused_hypothetical_cap_krw"], 500)
        self.assert_no_live_effects(value)

    def test_discount_only_excludes_points_cash(self):
        value = sample(policy="discount_only")
        self.assertEqual(value["points_candidate_krw"], 0)
        self.assertEqual(value["cash_equivalent_candidate_krw"], 0)
        self.assert_no_live_effects(value)

    def test_discount_plus_points_excludes_cash(self):
        value = sample(policy="discount_plus_points")
        self.assertEqual(value["points_candidate_krw"], 1000)
        self.assertEqual(value["cash_equivalent_candidate_krw"], 0)

    def test_cap_priority_discount_then_points_then_cash(self):
        value = sample(cap_krw=2500)
        self.assertEqual(value["discount_candidate_krw"], 2000)
        self.assertEqual(value["points_candidate_krw"], 500)
        self.assertEqual(value["cash_equivalent_candidate_krw"], 0)
        self.assertEqual(value["combined_candidate_krw"], 2500)

    def test_cap_cannot_exceed_gross(self):
        value = sample(gross_krw=100, cap_krw=9999)
        self.assertEqual(value["hypothetical_cap_krw"], 100)
        self.assertEqual(value["hypothetical_payable_after_discount_krw"], 0)
        self.assertEqual(value["combined_candidate_krw"], 100)

    def test_zero_gross_and_zero_cap(self):
        for kwargs in ({"gross_krw": 0}, {"cap_krw": 0}):
            value = sample(**kwargs)
            self.assertEqual(value["combined_candidate_krw"], 0)
            self.assert_no_live_effects(value)

    def test_discount_day30_and_day31(self):
        self.assertEqual(sample(age_days=30)["discount_candidate_krw"], 2000)
        self.assertEqual(sample(age_days=31)["discount_candidate_krw"], 0)

    def test_points_and_cash_day90_and_day91(self):
        self.assertEqual(sample(age_days=90)["points_candidate_krw"], 1000)
        self.assertEqual(sample(age_days=90)["cash_equivalent_candidate_krw"], 500)
        value = sample(age_days=91)
        self.assertEqual(value["combined_candidate_krw"], 0)
        self.assertTrue(value["points_and_cash_expired"])

    def test_expired_discount_does_not_consume_cap(self):
        value = sample(age_days=31, cap_krw=1000)
        self.assertEqual(value["discount_candidate_krw"], 0)
        self.assertEqual(value["points_candidate_krw"], 1000)

    def test_discount_reduces_hypothetical_payable_only(self):
        value = sample()
        self.assertEqual(value["hypothetical_payable_after_discount_krw"], 8000)
        self.assert_no_live_effects(value)

    def test_request_over_cap_never_overflows(self):
        value = sample(discount_request_krw=10**9,
                       points_request_krw=10**9,
                       cash_request_krw=10**9)
        self.assertEqual(value["combined_candidate_krw"], 4000)
        self.assertEqual(value["unused_hypothetical_cap_krw"], 0)

    def test_no_negative_candidate_or_payable(self):
        for policy in ("discount_only", "discount_plus_points",
                       "all_candidates"):
            value = sample(policy=policy, gross_krw=50, cap_krw=50)
            for key in ("discount_candidate_krw", "points_candidate_krw",
                        "cash_equivalent_candidate_krw",
                        "hypothetical_payable_after_discount_krw"):
                self.assertGreaterEqual(value[key], 0)
            self.assert_no_live_effects(value)

    def test_invalid_policy(self):
        for policy in ("payout", "", [], None):
            with self.assertRaises(ValueError):
                sample(policy=policy)

    def test_invalid_amounts_and_age(self):
        for key in ("gross_krw", "discount_request_krw",
                    "points_request_krw", "cash_request_krw",
                    "age_days", "cap_krw"):
            for bad in (-1, True, 10**9 + 1, 1.5):
                with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                    sample(**{key: bad})

    def test_all_options_never_authorize_real_benefit(self):
        for policy in ("discount_only", "discount_plus_points",
                       "all_candidates"):
            self.assert_no_live_effects(sample(policy=policy))


if __name__ == "__main__":
    unittest.main()
