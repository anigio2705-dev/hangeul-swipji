"""#120 regression matrix: integer KRW, multi-level referrals and refunds."""
import unittest

from team14_financial_edge_matrix import calculate_edge_case, _split_krw


def case(**overrides):
    args = {
        "gross_krw": 1000,
        "allocations": dict(teacher=700, platform=200, referral=70, benefit=30),
        "referral_weights": (3, 2, 1),
        "refunds": (),
        "already_paid_referral_krw": 0,
    }
    args.update(overrides)
    return calculate_edge_case(**args)


class Task120FinancialEdgeMatrixTests(unittest.TestCase):
    def test_multi_level_conserves_odd_won(self):
        result = case()
        self.assertEqual(70, sum(result["original_referral_level_krw"]))
        self.assertEqual(3, len(result["original_referral_level_krw"]))
        self.assertEqual(1000, result["remaining_transaction_krw"])

    def test_partial_then_full_refund_clears_every_bucket_and_level(self):
        result = case(refunds=(("partial_refund", 101),
                               ("partial_refund", 200),
                               ("full_refund", 699)))
        self.assertEqual(1000, result["total_refunded_krw"])
        self.assertEqual(0, result["remaining_transaction_krw"])
        self.assertEqual((0, 0, 0), result["remaining_referral_level_krw"])
        self.assertEqual(70, result["total_bucket_reversed_krw"]["referral"])
        self.assertEqual(1000, sum(result["total_bucket_reversed_krw"].values()))

    def test_7_won_3_then_1_then_3_regression(self):
        result = case(gross_krw=7,
                      allocations=dict(teacher=0, platform=1,
                                       referral=3, benefit=3),
                      referral_weights=(1, 1, 1),
                      refunds=(("partial_refund", 3),
                               ("partial_refund", 1),
                               ("full_refund", 3)))
        self.assertEqual(0, result["remaining_transaction_krw"])
        self.assertEqual((0, 0, 0), result["remaining_referral_level_krw"])
        for event in result["events"]:
            self.assertGreaterEqual(min(event["referral_level_reversed_krw"]), 0)
            self.assertEqual(event["refund_krw"],
                             sum(event["bucket_reversed_krw"].values()))

    def test_repeated_one_won_refunds_no_negative_rounding(self):
        result = case(gross_krw=9,
                      allocations=dict(teacher=3, platform=2,
                                       referral=3, benefit=1),
                      referral_weights=(5, 3, 2),
                      refunds=(("partial_refund", 1),) * 8 +
                              (("full_refund", 1),))
        self.assertEqual(9, result["total_refunded_krw"])
        self.assertEqual((0, 0, 0), result["remaining_referral_level_krw"])
        self.assertTrue(all(all(x >= 0 for x in event[
            "referral_level_reversed_krw"]) for event in result["events"]))

    def test_cancel_after_partial_refund(self):
        result = case(refunds=(("partial_refund", 333), ("cancel", 667)))
        self.assertEqual(0, result["remaining_transaction_krw"])

    def test_already_paid_referral_cancel_is_review_only(self):
        result = case(already_paid_referral_krw=50,
                      refunds=(("cancel", 1000),))
        self.assertEqual(50, result["potential_paid_exposure_krw"])
        self.assertTrue(result["manual_recovery_review_required"])
        self.assertFalse(result["automatic_clawback"])
        self.assertFalse(result["payout_authorized"])

    def test_no_refund_no_recovery_exposure(self):
        result = case(already_paid_referral_krw=50)
        self.assertEqual(0, result["potential_paid_exposure_krw"])
        self.assertFalse(result["manual_recovery_review_required"])

    def test_partial_refund_paid_exposure_bounded(self):
        result = case(already_paid_referral_krw=70,
                      refunds=(("partial_refund", 100),))
        self.assertLessEqual(result["potential_paid_exposure_krw"], 70)
        self.assertEqual(result["total_bucket_reversed_krw"]["referral"],
                         result["potential_paid_exposure_krw"])

    def test_referral_zero_across_multiple_levels(self):
        result = case(allocations=dict(teacher=800, platform=200,
                                       referral=0, benefit=0),
                      refunds=(("full_refund", 1000),))
        self.assertEqual((0, 0, 0), result["remaining_referral_level_krw"])

    def test_reject_over_refund_and_partial_full_balance(self):
        for refunds in (
            (("partial_refund", 1000),),
            (("full_refund", 999),),
            (("partial_refund", 900), ("partial_refund", 200)),
            (("cancel", 1001),),
        ):
            with self.subTest(refunds=refunds), self.assertRaises(ValueError):
                case(refunds=refunds)

    def test_reject_invalid_numeric_and_policy_inputs(self):
        for value in (-1, True, 71, 1001, "1"):
            with self.subTest(paid=value), self.assertRaises(ValueError):
                case(already_paid_referral_krw=value)
        for weights in ((), (0,), (1, True), (1, -1), ("2",),
                        tuple([1] * 9)):
            with self.subTest(weights=weights), self.assertRaises(ValueError):
                case(referral_weights=weights)
        for events in ((("refund", 1),), (("partial_refund", True),),
                       (("cancel", -1),), (("cancel", "1000"),)):
            with self.subTest(events=events), self.assertRaises(ValueError):
                case(refunds=events)

    def test_invalid_allocation_conservation(self):
        with self.assertRaises(ValueError):
            case(allocations=dict(teacher=700, platform=200,
                                  referral=70, benefit=29))
        with self.assertRaises(ValueError):
            case(allocations=dict(teacher=700, platform=200,
                                  referral=70, benefit=True))

    def test_split_exact_tie_and_zero(self):
        self.assertEqual((1, 1, 0), _split_krw(2, (1, 1, 1)))
        self.assertEqual((0, 0, 0), _split_krw(0, (0, 0, 0)))
        with self.assertRaises(ValueError):
            _split_krw(1, (0, 0, 0))

    def test_exhaustive_small_amounts_and_referral_levels(self):
        for gross in range(1, 24):
            for referral in range(gross + 1):
                alloc = dict(teacher=gross - referral, platform=0,
                             referral=referral, benefit=0)
                for first in range(gross):
                    result = case(
                        gross_krw=gross, allocations=alloc,
                        referral_weights=(1, 2, 3, 4),
                        refunds=((("partial_refund", first),
                                  ("full_refund", gross - first))
                                 if first else (("full_refund", gross),)))
                    self.assertEqual(0, result["remaining_transaction_krw"])
                    self.assertEqual((0, 0, 0, 0),
                                     result["remaining_referral_level_krw"])
                    self.assertEqual(gross, sum(
                        result["total_bucket_reversed_krw"].values()))

    def test_never_authorizes_real_money_or_policy(self):
        result = case(refunds=(("partial_refund", 5),))
        for flag in ("real_money", "policy_approved", "payment_enabled",
                     "refund_executed", "automatic_clawback",
                     "payout_authorized", "operating_db_connected"):
            self.assertIs(result[flag], False)


if __name__ == "__main__":
    unittest.main()
