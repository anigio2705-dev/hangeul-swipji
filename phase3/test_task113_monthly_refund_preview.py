"""#113 virtual monthly refund calculations; no real policy or money transfer."""
import unittest

from team14_monthly_refund_preview import simulate_monthly_refund


def sample(**changes):
    params = dict(list_price_krw=100000, discount_used_krw=20000,
                  total_lessons=10, completed_lessons=3,
                  unfulfilled_lessons=2, policy="net_paid_prorata")
    params.update(changes)
    return simulate_monthly_refund(**params)


class MonthlyRefundPreviewTests(unittest.TestCase):
    def assert_no_money(self, r):
        for k in ("legal_policy_approved", "refund_authorized", "payment_enabled",
                  "real_money", "booking_mutated", "ledger_mutated"):
            self.assertIs(r[k], False, k)

    def test_net_paid_prorata(self):
        r = sample()
        self.assertEqual(80000, r["net_paid_krw"])
        self.assertEqual(5, r["future_lessons"])
        self.assertEqual(7, r["candidate_unused_lessons"])
        self.assertEqual(56000, r["candidate_refund_krw"])
        self.assert_no_money(r)

    def test_gross_unused_less_discount(self):
        r = sample(policy="gross_unused_less_discount")
        self.assertEqual(50000, r["candidate_refund_krw"])
        self.assertEqual(30000, r["candidate_retained_krw"])
        self.assert_no_money(r)

    def test_no_discount_same_result(self):
        a = sample(discount_used_krw=0)
        b = sample(discount_used_krw=0, policy="gross_unused_less_discount")
        self.assertEqual(a["candidate_refund_krw"], b["candidate_refund_krw"])

    def test_all_completed_refund_zero(self):
        for policy in ("net_paid_prorata", "gross_unused_less_discount"):
            r = sample(completed_lessons=10, unfulfilled_lessons=0, policy=policy)
            self.assertEqual(0, r["candidate_refund_krw"])
            self.assert_no_money(r)

    def test_no_completed_maximum_net_paid(self):
        for policy in ("net_paid_prorata", "gross_unused_less_discount"):
            r = sample(completed_lessons=0, unfulfilled_lessons=0, policy=policy)
            self.assertEqual(80000, r["candidate_refund_krw"])

    def test_all_nonperformance_counted_separately(self):
        r = sample(completed_lessons=0, unfulfilled_lessons=10)
        self.assertEqual(0, r["future_lessons"])
        self.assertEqual(10, r["candidate_unused_lessons"])
        self.assert_no_money(r)

    def test_zero_price_and_discount(self):
        r = sample(list_price_krw=0, discount_used_krw=0)
        self.assertEqual(0, r["candidate_refund_krw"])

    def test_full_discount_no_refund(self):
        r = sample(discount_used_krw=100000)
        self.assertEqual(0, r["candidate_refund_krw"])

    def test_half_up_rounding_won(self):
        r = sample(list_price_krw=1, discount_used_krw=0,
                   total_lessons=2, completed_lessons=1, unfulfilled_lessons=0)
        self.assertEqual(1, r["candidate_refund_krw"])

    def test_integer_rounding_large_amount(self):
        r = sample(list_price_krw=1000000000, discount_used_krw=1,
                   total_lessons=3, completed_lessons=1, unfulfilled_lessons=1)
        self.assertLessEqual(r["candidate_refund_krw"], r["net_paid_krw"])
        self.assert_no_money(r)

    def test_invalid_money_types_and_range(self):
        for change in ({"list_price_krw": -1}, {"discount_used_krw": True},
                       {"list_price_krw": 1.5}, {"list_price_krw": 1000000001},
                       {"discount_used_krw": 100001}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                sample(**change)

    def test_invalid_counts(self):
        for change in ({"total_lessons": 0}, {"total_lessons": 367},
                       {"completed_lessons": 11}, {"unfulfilled_lessons": 8},
                       {"completed_lessons": True}, {"unfulfilled_lessons": -1}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                sample(**change)

    def test_invalid_policy(self):
        for policy in ("approved", "", None, [], 1):
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                sample(policy=policy)

    def test_single_lesson_boundary(self):
        r = sample(total_lessons=1, completed_lessons=0,
                   unfulfilled_lessons=1)
        self.assertEqual(80000, r["candidate_refund_krw"])

    def test_candidate_only_even_when_all_data_present(self):
        for policy in ("net_paid_prorata", "gross_unused_less_discount"):
            r = sample(policy=policy)
            self.assert_no_money(r)
            self.assertNotIn("refund_executed", r)


if __name__ == "__main__":
    unittest.main()
