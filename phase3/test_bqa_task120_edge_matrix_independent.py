"""B/15 independent #120: exact-WON multi-level/refund invariant and no-live-money gate."""
import unittest
from team14_financial_edge_matrix import calculate_edge_case, _split_krw

def run(gross, referral, refunds=(), weights=(1,2,3), paid=0):
    return calculate_edge_case(
        gross_krw=gross,
        allocations={"teacher":gross-referral,"platform":0,
                     "referral":referral,"benefit":0},
        referral_weights=weights,refunds=refunds,
        already_paid_referral_krw=paid)

class BQA120EdgeMatrix(unittest.TestCase):
    def test_small_odd_krw_all_level_counts_conserve(self):
        for gross in range(1,12):
            for referral in range(gross+1):
                for count in (1,2,3,5,8):
                    with self.subTest(gross=gross,referral=referral,count=count):
                        state=run(gross,referral,weights=tuple(range(1,count+1)))
                        self.assertEqual(referral,sum(state["original_referral_level_krw"]))
                        self.assertEqual(gross,state["remaining_transaction_krw"])
                        self.assertEqual(0,state["potential_paid_exposure_krw"])
    def test_repeated_one_won_then_cancel_zero_balances(self):
        for gross in range(2,12):
            for referral in range(gross+1):
                events=(("partial_refund",1),)*(gross-1)+(("cancel",1),)
                state=run(gross,referral,events,weights=(7,3,1,2))
                self.assertEqual(gross,state["total_refunded_krw"])
                self.assertEqual(0,state["remaining_transaction_krw"])
                self.assertEqual((0,0,0,0),state["remaining_referral_level_krw"])
                self.assertEqual(referral,state["total_bucket_reversed_krw"]["referral"])
                for event in state["events"]:
                    self.assertEqual(event["refund_krw"],
                                     sum(event["bucket_reversed_krw"].values()))
                    self.assertGreaterEqual(min(event["referral_level_reversed_krw"]),0)
    def test_paid_then_full_cancel_only_flags_manual_review(self):
        state=run(9,5,(("cancel",9),),weights=(3,2,1),paid=4)
        self.assertEqual(4,state["potential_paid_exposure_krw"])
        self.assertTrue(state["manual_recovery_review_required"])
        for key in ("real_money","policy_approved","payment_enabled",
                    "refund_executed","automatic_clawback","payout_authorized",
                    "operating_db_connected"):
            self.assertIs(state[key],False)
    def test_paid_then_small_partial_refund_exposure_bounded(self):
        state=run(13,7,(("partial_refund",1),),paid=7)
        self.assertLessEqual(state["potential_paid_exposure_krw"],7)
        self.assertEqual(state["total_bucket_reversed_krw"]["referral"],
                         state["potential_paid_exposure_krw"])
        self.assertFalse(state["automatic_clawback"])
    def test_over_refund_after_partial_rejected(self):
        for gross in (3,7,11):
            with self.subTest(gross=gross),self.assertRaises(ValueError):
                run(gross,1,(("partial_refund",gross-1),
                             ("partial_refund",2)))
    def test_reject_float_bool_string_or_negative_amounts(self):
        for bad in (True,False,1.0,"1",-1,None):
            with self.subTest(bad=bad),self.assertRaises((ValueError,TypeError)):
                run(7,3,(("partial_refund",bad),))
    def test_referral_weights_are_test_only_not_policy(self):
        for bad in ((0,1),(1,0),(-1,1),(1,True),(1,"2"),tuple([1]*9)):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                run(7,3,weights=bad)
    def test_largest_remainder_tie_deterministic(self):
        self.assertEqual((1,1,0,0),_split_krw(2,(1,1,1,1)))
        self.assertEqual((0,0,0,0),_split_krw(0,(1,1,1,1)))
        self.assertEqual(5,sum(_split_krw(5,(1,3,2,4))))
    def test_refund_replay_semantics_no_negative_levels(self):
        state=run(7,3,(("partial_refund",3),("partial_refund",1),
                         ("full_refund",3)),weights=(1,1,1))
        self.assertEqual((0,0,0),state["remaining_referral_level_krw"])
        self.assertEqual(7,sum(x["refund_krw"] for x in state["events"]))
        self.assertFalse(state["payout_authorized"])

if __name__=="__main__":
    unittest.main()
