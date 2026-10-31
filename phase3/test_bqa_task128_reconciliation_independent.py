"""B/15 independent QA-only for #128 exact product SHA
2053e7c1920ac31389515e3fd45b7cec7c28a2a7.
Mock records only; no provider, live payment, DB or payout."""
import copy
import unittest
from team14_reconciliation_review import reconcile_booking

B = "book_128"
def evt(i, amount, state="succeeded", booking=B):
    return {"id":i,"booking_id":booking,"amount_krw":amount,"state":state}
def line(i, kind, amount, booking=B):
    return {"id":i,"booking_id":booking,"kind":kind,"amount_krw":amount}
def inputs():
    return dict(booking_id=B,
        payments=[evt("p1", 700),evt("p2",300)],
        refunds=[evt("r1",100)],
        payouts=[evt("o1",400,"paid")],
        ledger=[line("l1","payment",1000),line("l2","refund",-100),line("l3","payout",-400)],
        trusted_evidence_verified=True, policy_approved=True)
def call(**changes):
    data=inputs();data.update(changes)
    return reconcile_booking(**data)

class IndependentReconciliationQA(unittest.TestCase):
    def assert_hold(self, result, reason):
        self.assertEqual(result["status"],"HOLD")
        self.assertIs(result["payout_hold_required"],True)
        self.assertIn(reason,result["reasons"])
        self.assertIs(result["payout_execution_enabled"],False)
        self.assertIs(result["real_payment_enabled"],False)
        self.assertIs(result["operating_db_connected"],False)

    def test_01_split_payment_match_remains_review_only(self):
        v=call()
        self.assertEqual(v["status"],"MATCHED_REVIEW_ONLY")
        self.assertEqual((v["gross_krw"],v["refund_krw"],v["disbursed_krw"],v["unsettled_krw"]),(1000,100,400,500))
        self.assertIs(v["payout_execution_enabled"],False)
        self.assertIs(v["real_payment_enabled"],False)

    def test_02_payment_ledger_mismatch_holds(self):
        self.assert_hold(call(payments=[evt("p1",700),evt("p2",301)]),"PAYMENT_LEDGER_MISMATCH")

    def test_03_refund_ledger_mismatch_holds(self):
        self.assert_hold(call(refunds=[evt("r1",101)]),"REFUND_LEDGER_MISMATCH")

    def test_04_paid_payout_ledger_mismatch_holds(self):
        self.assert_hold(call(payouts=[evt("o1",401,"paid")]),"PAYOUT_LEDGER_MISMATCH")

    def test_05_repeated_refund_exceeding_gross_holds(self):
        self.assert_hold(call(refunds=[evt("r1",600),evt("r2",500)]),"REFUND_EXCEEDS_PAYMENT")

    def test_06_payout_exceeding_net_receipts_holds(self):
        self.assert_hold(call(payouts=[evt("o1",901,"paid")]),"PAYOUT_EXCEEDS_NET_RECEIPTS")

    def test_07_duplicate_payment_event_holds_even_if_totals_match(self):
        self.assert_hold(call(payments=[evt("p1",700),evt("p1",300)]),"payment_DUPLICATE_ID")

    def test_08_cross_booking_refund_holds(self):
        self.assert_hold(call(refunds=[evt("r1",100,booking="other")]),"refund_FOREIGN_BOOKING")

    def test_09_cross_booking_payout_holds(self):
        self.assert_hold(call(payouts=[evt("o1",400,"paid",booking="other")]),"payout_FOREIGN_BOOKING")

    def test_10_duplicate_ledger_identity_holds(self):
        self.assert_hold(call(ledger=[line("same","payment",1000),line("same","refund",-100),line("o","payout",-400)]),"ledger_DUPLICATE_ID")

    def test_11_invalid_ledger_sign_holds(self):
        self.assert_hold(call(ledger=[line("l1","payment",-1000),line("l2","refund",-100),line("l3","payout",-400)]),"ledger_INVALID_SIGN")

    def test_12_pending_failed_payouts_hold(self):
        for state,reason in (("pending","PENDING_PAYOUT_REVIEW_REQUIRED"),("failed","FAILED_PAYOUT_REVIEW_REQUIRED")):
            with self.subTest(state=state):
                self.assert_hold(call(payouts=[evt("o1",400,state)],ledger=[line("l1","payment",1000),line("l2","refund",-100)]),reason)

    def test_13_untrusted_evidence_or_policy_holds(self):
        self.assert_hold(call(trusted_evidence_verified=False),"TRUSTED_EVIDENCE_MISSING")
        self.assert_hold(call(policy_approved=False),"APPROVED_POLICY_MISSING")

    def test_14_rejects_boolean_float_negative_or_huge_amounts(self):
        for amount in (True,1.5,-1,"100",10**13):
            with self.subTest(amount=amount),self.assertRaises(ValueError):
                call(refunds=[evt("r1",amount)])

    def test_15_rejects_invalid_identity_and_schema(self):
        for bid in ("../x","",True,None,"a"*65):
            with self.subTest(bid=bid),self.assertRaises(ValueError):
                call(booking_id=bid)
        bad=evt("p1",700);bad["extra"]="untrusted"
        with self.assertRaises(ValueError):call(payments=[bad])

    def test_16_rejects_truthy_forged_boolean_flags(self):
        for field in ("trusted_evidence_verified","policy_approved"):
            for bad in (1,"true",None,[],{}):
                with self.subTest(field=field,bad=bad),self.assertRaises(ValueError):
                    call(**{field:bad})

    def test_17_does_not_mutate_caller_evidence(self):
        data=inputs();before=copy.deepcopy(data)
        reconcile_booking(**data)
        self.assertEqual(data,before)

if __name__=="__main__":
    unittest.main()
