"""B/15 QA-only adversarial matrix for #113 exact product SHA 25150230..."""
import itertools
import unittest

from team14_monthly_refund_preview import simulate_monthly_refund, POLICIES

DENY = ("legal_policy_approved", "refund_authorized", "payment_enabled",
        "real_money", "booking_mutated", "ledger_mutated")


def run(**kw):
    d = dict(list_price_krw=100000, discount_used_krw=20000,
             total_lessons=10, completed_lessons=3,
             unfulfilled_lessons=2, policy="net_paid_prorata")
    d.update(kw)
    return simulate_monthly_refund(**d)


class BIndependentTask113Tests(unittest.TestCase):
    def no_real_money(self, r):
        for k in DENY:
            self.assertIs(r[k], False, k)
        self.assertNotIn("refund_executed", r)

    def test_exhaustive_small_month_counts_and_conservation(self):
        for total in range(1, 9):
            for completed in range(total + 1):
                for undelivered in range(total - completed + 1):
                    for policy in POLICIES:
                        r = run(total_lessons=total, completed_lessons=completed,
                                unfulfilled_lessons=undelivered, policy=policy)
                        self.assertEqual(total - completed - undelivered, r["future_lessons"])
                        self.assertEqual(total - completed, r["candidate_unused_lessons"])
                        self.assertEqual(80000, r["net_paid_krw"])
                        self.assertEqual(80000, r["candidate_refund_krw"] +
                                         r["candidate_retained_krw"])
                        self.assertGreaterEqual(r["candidate_refund_krw"], 0)
                        self.assertLessEqual(r["candidate_refund_krw"], 80000)
                        self.no_real_money(r)

    def test_refund_monotone_as_completed_lessons_increase(self):
        for policy in POLICIES:
            values = [run(total_lessons=20, completed_lessons=n,
                          unfulfilled_lessons=0, policy=policy)["candidate_refund_krw"]
                      for n in range(21)]
            self.assertEqual(sorted(values, reverse=True), values)
            self.assertEqual(80000, values[0])
            self.assertEqual(0, values[-1])

    def test_full_discount_and_zero_price_always_zero(self):
        for policy in POLICIES:
            for price, discount in ((0, 0), (1, 1), (100000, 100000)):
                r = run(list_price_krw=price, discount_used_krw=discount, policy=policy)
                self.assertEqual(0, r["candidate_refund_krw"])
                self.no_real_money(r)

    def test_zero_discount_policies_match_across_matrix(self):
        for total, completed in itertools.product((1, 2, 3, 10, 99), (0, 1, 2)):
            if completed > total:
                continue
            a = run(discount_used_krw=0, total_lessons=total,
                    completed_lessons=completed, unfulfilled_lessons=0,
                    policy="net_paid_prorata")
            b = run(discount_used_krw=0, total_lessons=total,
                    completed_lessons=completed, unfulfilled_lessons=0,
                    policy="gross_unused_less_discount")
            self.assertEqual(a["candidate_refund_krw"], b["candidate_refund_krw"])

    def test_half_up_rounding_at_exact_half_won(self):
        for policy in POLICIES:
            r = run(list_price_krw=1, discount_used_krw=0, total_lessons=2,
                    completed_lessons=1, unfulfilled_lessons=0, policy=policy)
            self.assertEqual(1, r["candidate_refund_krw"])
            self.no_real_money(r)

    def test_extreme_valid_price_and_month(self):
        for policy in POLICIES:
            r = run(list_price_krw=1000000000, discount_used_krw=999999999,
                    total_lessons=366, completed_lessons=183,
                    unfulfilled_lessons=183, policy=policy)
            self.assertGreaterEqual(r["candidate_refund_krw"], 0)
            self.assertLessEqual(r["candidate_refund_krw"], 1)
            self.no_real_money(r)

    def test_reject_type_coercion_and_overflow(self):
        for kw in ({"list_price_krw": True}, {"discount_used_krw": 1.5},
                   {"total_lessons": False}, {"completed_lessons": "3"},
                   {"unfulfilled_lessons": -1}, {"list_price_krw": -1},
                   {"discount_used_krw": 100001}, {"total_lessons": 0},
                   {"total_lessons": 367}, {"completed_lessons": 11},
                   {"unfulfilled_lessons": 8}, {"list_price_krw": 1000000001},
                   {"policy": None}, {"policy": []}, {"policy": "approved"}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                run(**kw)

    def test_full_completion_zero_and_full_unused_never_overpaid(self):
        for policy in POLICIES:
            completed = run(total_lessons=10, completed_lessons=10,
                            unfulfilled_lessons=0, policy=policy)
            unused = run(total_lessons=10, completed_lessons=0,
                         unfulfilled_lessons=10, policy=policy)
            self.assertEqual(0, completed["candidate_refund_krw"])
            self.assertEqual(80000, unused["candidate_refund_krw"])
            self.no_real_money(completed)
            self.no_real_money(unused)

    def test_candidate_only_not_live_authorization(self):
        for policy in POLICIES:
            r = run(policy=policy)
            self.assertEqual("HALF_UP_WON", r["rounding"])
            self.assertEqual(policy, r["policy"])
            self.no_real_money(r)


if __name__ == "__main__":
    unittest.main()
