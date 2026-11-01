"""#128 A regressions: isolated four-way reconciliation and no payout release."""
import os
import tempfile
import unittest

from team14_reversal_subledger import SimulatedReversalLedger
from team14_reconciliation_hold import reconcile_review_statements


def record(ledger, tx_id="tx1", evidence_id="pay1", gross=1000,
           teacher=700, platform=200, referral=30, benefit=70):
    return ledger.record(tx_id=tx_id, evidence_id=evidence_id, gross_krw=gross,
                         teacher_krw=teacher, platform_krw=platform,
                         referral_krw=referral, benefit_krw=benefit)


class Task128ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.ledger = SimulatedReversalLedger()
        record(self.ledger)
        self.payments = [dict(tx_id="tx1", evidence_id="pay1", amount_krw=1000)]
        self.refunds = []
        self.payouts = [dict(tx_id="tx1", teacher_net_krw=700)]

    def tearDown(self):
        self.ledger.close()

    def check(self, *, payments=None, refunds=None, payouts=None):
        return reconcile_review_statements(
            ledger=self.ledger,
            payments=self.payments if payments is None else payments,
            refunds=self.refunds if refunds is None else refunds,
            payouts=self.payouts if payouts is None else payouts)

    def assert_held(self, result):
        self.assertEqual(128, result["task"])
        for field in ("payout_hold",):
            self.assertIs(result[field], True)
        for field in ("provider_provenance_verified", "operator_approval_verified",
                      "payout_authorized", "real_money_enabled",
                      "operating_db_connected", "external_api_called"):
            self.assertIs(result[field], False, field)

    def test_exact_four_way_match_still_no_real_payout(self):
        result = self.check()
        self.assertEqual("MATCHED_REVIEW_ONLY", result["status"])
        self.assertFalse(result["discrepancy_hold"])
        self.assertEqual([], result["discrepancies"])
        self.assertEqual((1, 0), (result["transactions_checked"],
                                  result["refunds_checked"]))
        self.assert_held(result)

    def test_partial_refund_reconciles_reversal_bucket_teacher_net(self):
        self.ledger.reverse(reversal_id="r1", tx_id="tx1",
                            evidence_id="ref1", event_kind="partial_refund",
                            refund_krw=250)
        reversed_teacher = self.ledger.read_reversal("r1")["reversed_entries"][0]["amount_krw"]
        result = self.check(
            refunds=[dict(reversal_id="r1", tx_id="tx1",
                          evidence_id="ref1", amount_krw=250)],
            payouts=[dict(tx_id="tx1", teacher_net_krw=700-reversed_teacher)])
        self.assertEqual("MATCHED_REVIEW_ONLY", result["status"])
        self.assertEqual(1, result["refunds_checked"])
        self.assert_held(result)

    def test_full_refund_zero_teacher_payout_is_matched_not_released(self):
        self.ledger.reverse(reversal_id="r1", tx_id="tx1",
                            evidence_id="ref1", event_kind="full_refund",
                            refund_krw=1000)
        result = self.check(
            refunds=[dict(reversal_id="r1", tx_id="tx1",
                          evidence_id="ref1", amount_krw=1000)],
            payouts=[dict(tx_id="tx1", teacher_net_krw=0)])
        self.assertEqual("MATCHED_REVIEW_ONLY", result["status"])
        self.assert_held(result)

    def test_payment_amount_mismatch_holds(self):
        result = self.check(payments=[dict(tx_id="tx1", evidence_id="pay1",
                                           amount_krw=999)])
        self.assertIn("PAYMENT_MISMATCH:tx1", result["discrepancies"])
        self.assertTrue(result["discrepancy_hold"])
        self.assert_held(result)

    def test_payment_evidence_mismatch_holds(self):
        result = self.check(payments=[dict(tx_id="tx1", evidence_id="fake",
                                           amount_krw=1000)])
        self.assertIn("PAYMENT_MISMATCH:tx1", result["discrepancies"])

    def test_missing_payment_holds(self):
        self.assertIn("MISSING_PAYMENT:tx1", self.check(payments=[])["discrepancies"])

    def test_unknown_payment_holds(self):
        result = self.check(payments=self.payments + [
            dict(tx_id="tx2", evidence_id="pay2", amount_krw=100)])
        self.assertIn("UNKNOWN_TRANSACTION:tx2", result["discrepancies"])

    def test_missing_payout_statement_holds(self):
        self.assertIn("MISSING_PAYOUT_STATEMENT:tx1",
                      self.check(payouts=[])["discrepancies"])

    def test_wrong_teacher_net_holds(self):
        self.assertIn("PAYOUT_MISMATCH:tx1",
                      self.check(payouts=[dict(tx_id="tx1", teacher_net_krw=701)])[
                          "discrepancies"])

    def test_refund_missing_holds(self):
        self.ledger.reverse(reversal_id="r1", tx_id="tx1",
                            evidence_id="ref1", event_kind="partial_refund",
                            refund_krw=1)
        self.assertIn("MISSING_REFUND:r1", self.check()["discrepancies"])

    def test_refund_evidence_and_amount_mismatch_holds(self):
        self.ledger.reverse(reversal_id="r1", tx_id="tx1",
                            evidence_id="ref1", event_kind="partial_refund",
                            refund_krw=1)
        for wrong in (dict(reversal_id="r1", tx_id="tx1", evidence_id="bad",
                           amount_krw=1),
                      dict(reversal_id="r1", tx_id="tx1", evidence_id="ref1",
                           amount_krw=2)):
            with self.subTest(wrong=wrong):
                self.assertIn("REFUND_MISMATCH:r1",
                              self.check(refunds=[wrong])["discrepancies"])

    def test_unknown_refund_holds(self):
        self.assertIn("UNKNOWN_REFUND:r2",
                      self.check(refunds=[dict(reversal_id="r2", tx_id="tx1",
                                               evidence_id="ref2", amount_krw=1)])[
                          "discrepancies"])

    def test_duplicate_ids_fail_closed(self):
        for key, args in (("payment", dict(payments=self.payments*2)),
                          ("refund", dict(refunds=[dict(reversal_id="r1",
                                                       tx_id="tx1", evidence_id="e1",
                                                       amount_krw=1)]*2)),
                          ("payout", dict(payouts=self.payouts*2))):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.check(**args)

    def test_invalid_id_types_and_amounts_fail_closed(self):
        for bad in (None, [], {"x": 1}, True, 1, "../evil"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.check(payments=[dict(tx_id=bad, evidence_id="pay1",
                                          amount_krw=1000)])
        for bad in (None, True, -1, "1000", 10**13, 1.5):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.check(payouts=[dict(tx_id="tx1", teacher_net_krw=bad)])

    def test_unknown_or_missing_fields_fail_closed(self):
        with self.assertRaises(ValueError):
            self.check(payments=[dict(tx_id="tx1", amount_krw=1000)])
        with self.assertRaises(ValueError):
            self.check(payouts=[dict(tx_id="tx1", teacher_net_krw=700,
                                     release=True)])

    def test_no_mutation_of_immutable_ledger(self):
        before = (self.ledger.db.execute("SELECT COUNT(*) FROM sim_tx").fetchone()[0],
                  self.ledger.db.execute("SELECT COUNT(*) FROM sim_entry").fetchone()[0])
        self.check()
        after = (self.ledger.db.execute("SELECT COUNT(*) FROM sim_tx").fetchone()[0],
                 self.ledger.db.execute("SELECT COUNT(*) FROM sim_entry").fetchone()[0])
        self.assertEqual(before, after)

    def test_multiple_transactions_must_all_be_present(self):
        record(self.ledger, tx_id="tx2", evidence_id="pay2", gross=100,
               teacher=50, platform=50, referral=0, benefit=0)
        result = self.check()
        self.assertIn("MISSING_PAYMENT:tx2", result["discrepancies"])
        self.assertIn("MISSING_PAYOUT_STATEMENT:tx2", result["discrepancies"])
        ok = self.check(
            payments=self.payments+[dict(tx_id="tx2", evidence_id="pay2", amount_krw=100)],
            payouts=self.payouts+[dict(tx_id="tx2", teacher_net_krw=50)])
        self.assertEqual("MATCHED_REVIEW_ONLY", ok["status"])
        self.assert_held(ok)

    def test_persisted_simulated_ledger_reconciles_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "review.sqlite")
            first = SimulatedReversalLedger(path)
            try:
                record(first, tx_id="persist", evidence_id="p", gross=10,
                       teacher=8, platform=2, referral=0, benefit=0)
            finally:
                first.close()
            second = SimulatedReversalLedger(path)
            try:
                result = reconcile_review_statements(
                    ledger=second,
                    payments=[dict(tx_id="persist", evidence_id="p", amount_krw=10)],
                    refunds=[],
                    payouts=[dict(tx_id="persist", teacher_net_krw=8)])
                self.assertEqual("MATCHED_REVIEW_ONLY", result["status"])
                self.assert_held(result)
            finally:
                second.close()


    def test_forged_reversal_missing_three_buckets_cannot_match(self):
        # Raw SQL is intentionally used to simulate an incomplete ledger
        # record bypassing the #115 API. Aggregate totals still reconcile.
        self.ledger.db.execute(
            "INSERT INTO sim_reversal VALUES(?,?,?,?,?,?)",
            ("r_forged", "tx1", "refund1", "partial_refund", 100, "untrusted"))
        self.ledger.db.execute(
            "INSERT INTO sim_reversal_entry VALUES(?,?,?)",
            ("r_forged", "teacher", 100))
        result = self.check(
            refunds=[dict(reversal_id="r_forged", tx_id="tx1",
                          evidence_id="refund1", amount_krw=100)],
            payouts=[dict(tx_id="tx1", teacher_net_krw=600)])
        self.assertIn("REVERSAL_ENTRY_MISMATCH:r_forged",
                      result["discrepancies"])
        self.assertEqual("DISCREPANCY_HOLD", result["status"])
        self.assert_held(result)

    def test_forged_four_bucket_reversal_with_wrong_sum_is_held(self):
        self.ledger.db.execute(
            "INSERT INTO sim_reversal VALUES(?,?,?,?,?,?)",
            ("r_wrong", "tx1", "refund1", "partial_refund", 100, "untrusted"))
        self.ledger.db.executemany(
            "INSERT INTO sim_reversal_entry VALUES(?,?,?)",
            [("r_wrong", bucket, 90 if bucket == "teacher" else 0)
             for bucket in ("teacher", "platform", "referral", "benefit")])
        result = self.check(
            refunds=[dict(reversal_id="r_wrong", tx_id="tx1",
                          evidence_id="refund1", amount_krw=100)],
            payouts=[dict(tx_id="tx1", teacher_net_krw=610)])
        self.assertIn("REVERSAL_ENTRY_MISMATCH:r_wrong",
                      result["discrepancies"])
        self.assert_held(result)


if __name__ == "__main__":
    unittest.main()
