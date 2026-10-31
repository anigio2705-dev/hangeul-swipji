"""B/15 independent #115 adversarial QA: monotone refunds, no double deduction."""
import unittest
from team14_reversal_subledger import SimulatedReversalLedger

class BQA115Reversal(unittest.TestCase):
    def setUp(self):
        self.ledger=SimulatedReversalLedger()
    def tearDown(self):
        self.ledger.close()
    def seed(self, **kw):
        args=dict(tx_id="qa_tx",evidence_id="qa_capture",gross_krw=7,
                  teacher_krw=0,platform_krw=1,referral_krw=3,benefit_krw=3)
        args.update(kw)
        return self.ledger.record(**args)
    def reverse(self, n, amount, kind="partial_refund"):
        return self.ledger.reverse(reversal_id="qa_rev"+str(n),tx_id="qa_tx",
                                   evidence_id="qa_refund"+str(n),
                                   event_kind=kind,refund_krw=amount)
    def test_largest_remainder_allocation_must_never_decrease_prior_bucket(self):
        """7 KRW (0,1,3,3): refund 3 then 1 is valid; Alabama paradox must not block."""
        self.seed()
        first=self.reverse(1,3)
        second=self.reverse(2,1)
        self.assertEqual(3,first["cumulative_refunded_krw"])
        self.assertEqual(4,second["cumulative_refunded_krw"])
        self.assertEqual(3,second["remaining_krw"])
        self.assertEqual(4,sum(e["amount_krw"] for r in (first,second)
                               for e in r["reversed_entries"]))
    def test_full_reversal_after_multiple_partials_conserves_all_buckets(self):
        self.seed()
        for n,amount,kind in ((1,1,"partial_refund"),(2,2,"partial_refund"),
                              (3,4,"full_refund")):
            result=self.reverse(n,amount,kind)
        self.assertEqual(7,result["cumulative_refunded_krw"])
        self.assertEqual(0,result["remaining_krw"])
    def test_same_reversal_id_conflict_does_not_write_twice(self):
        self.seed()
        self.reverse(1,1)
        with self.assertRaises(ValueError):
            self.reverse(1,2)
        self.assertEqual(1,self.ledger.db.execute("SELECT count(*) FROM sim_reversal").fetchone()[0])
    def test_over_refund_after_partial_rejected(self):
        self.seed()
        self.reverse(1,3)
        with self.assertRaises(ValueError):
            self.reverse(2,5)
        self.assertEqual(4,self.ledger.read_reversal("qa_rev1")["remaining_krw"])
    def test_all_money_authorization_flags_false(self):
        self.seed()
        r=self.reverse(1,1)
        for k in ("real_money","policy_approved","payment_enabled","refund_executed",
                  "payout_authorized","operating_db_connected"):
            self.assertIs(r[k],False)
    def test_invalid_refund_types_rejected(self):
        self.seed()
        for bad in (True,1.2,"1",0,-1,None):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                self.reverse(1,bad)
    def test_cancel_requires_exact_remaining_balance(self):
        self.seed()
        self.reverse(1,3)
        with self.assertRaises(ValueError):
            self.reverse(2,3,"cancel")
        r=self.reverse(2,4,"cancel")
        self.assertEqual(0,r["remaining_krw"])
    def test_no_cross_transaction_reversal(self):
        self.seed()
        self.ledger.record(tx_id="another",evidence_id="another_evt",gross_krw=1,
                           teacher_krw=1,platform_krw=0,referral_krw=0,benefit_krw=0)
        self.reverse(1,1)
        self.assertEqual(1,self.ledger.read("another")["gross_krw"])

if __name__=="__main__":
    unittest.main()
