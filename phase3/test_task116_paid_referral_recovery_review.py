"""#116 independent-from-payment simulation contract regression."""
import unittest

from team14_paid_referral_recovery_review import review_paid_referral_recovery


def example(**kw):
    values = dict(
        gross_krw=100, allocations=dict(teacher=60, platform=20,
                                       referral=15, benefit=5),
        referral_weights=(3, 2, 1),
        refunds=(("full_refund", 100),),
        already_paid_referral_krw=12,
        available_balance_fixture_krw=3,
        future_settlement_fixture_krw=4,
    )
    values.update(kw)
    return review_paid_referral_recovery(**values)


class Task116RecoveryReviewTests(unittest.TestCase):
    def test_full_refund_three_alternatives_conserve_exposure(self):
        x = example()
        self.assertEqual(12, x["potential_exposure_krw"])
        self.assertEqual([3, 4, 5], [a["illustrative_krw"] for a in x["alternatives"]])
        self.assertEqual("MANUAL_REVIEW_REQUIRED", x["recommended_state"])

    def test_no_refund_no_recovery(self):
        x = example(refunds=())
        self.assertEqual(0, x["potential_exposure_krw"])
        self.assertEqual([0, 0, 0], [a["illustrative_krw"] for a in x["alternatives"]])
        self.assertEqual("NO_ACTION", x["recommended_state"])

    def test_no_paid_reward_no_exposure(self):
        x = example(already_paid_referral_krw=0)
        self.assertEqual(0, x["potential_exposure_krw"])

    def test_partial_refund_bounds_exposure(self):
        x = example(refunds=(("partial_refund", 10),))
        self.assertLessEqual(x["potential_exposure_krw"], 12)
        self.assertLessEqual(sum(a["illustrative_krw"] for a in x["alternatives"]),
                             x["potential_exposure_krw"])

    def test_fixture_cap_is_not_legal_authorization(self):
        x = example(recovery_cap_fixture_krw=5)
        self.assertEqual(5, x["illustrative_recovery_ceiling_krw"])
        self.assertEqual(7, x["not_in_illustrative_scope_krw"])
        self.assertEqual([3, 2, 0], [a["illustrative_krw"] for a in x["alternatives"]])
        self.assertFalse(x["recovery_cap_verified"])
        self.assertEqual(0, x["approved_recovery_krw"])

    def test_zero_cap_never_debits(self):
        x = example(recovery_cap_fixture_krw=0)
        self.assertEqual(0, x["illustrative_recovery_ceiling_krw"])
        self.assertEqual(0, x["actual_balance_debited_krw"])

    def test_huge_fixture_balances_never_exceed_exposure(self):
        x = example(available_balance_fixture_krw=10**12,
                    future_settlement_fixture_krw=10**12)
        self.assertEqual([12, 0, 0], [a["illustrative_krw"] for a in x["alternatives"]])

    def test_invalid_fixtures_fail_closed(self):
        for v in (True, -1, 1.5, "5", None, 10**12 + 1):
            with self.subTest(value=v):
                with self.assertRaises(ValueError):
                    example(available_balance_fixture_krw=v)
                with self.assertRaises(ValueError):
                    example(future_settlement_fixture_krw=v)
                with self.assertRaises(ValueError):
                    example(recovery_cap_fixture_krw=v)

    def test_odd_won_refund_regression(self):
        x = example(gross_krw=7,
                    allocations=dict(teacher=0, platform=1, referral=3, benefit=3),
                    referral_weights=(1, 1, 1),
                    refunds=(("partial_refund", 3), ("partial_refund", 1),
                             ("full_refund", 3)),
                    already_paid_referral_krw=3,
                    available_balance_fixture_krw=1,
                    future_settlement_fixture_krw=1)
        self.assertEqual(3, x["potential_exposure_krw"])
        self.assertEqual([1, 1, 1], [a["illustrative_krw"] for a in x["alternatives"]])

    def test_real_money_never_authorized(self):
        x = example(recovery_cap_fixture_krw=12)
        for key in ("automatic_clawback", "policy_approved",
                    "legal_recovery_approved", "real_money",
                    "payout_authorized", "operating_db_connected",
                    "recovery_cap_verified"):
            self.assertIs(x[key], False)
        for key in ("approved_recovery_krw", "actual_balance_debited_krw",
                    "actual_future_settlement_offset_krw", "actual_recovered_krw"):
            self.assertEqual(0, x[key])
        self.assertTrue(x["simulation_only"])

    def test_overpaid_fixture_rejected_by_source_calculator(self):
        with self.assertRaises(ValueError):
            example(already_paid_referral_krw=16)


if __name__ == "__main__":
    unittest.main()
