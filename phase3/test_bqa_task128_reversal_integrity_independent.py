"""B/15 independent QA replay #128 repaired exact A SHA 3bb601120bbc2b908fce680c13d00abad02c060a; tests only."""
import unittest

from team14_reversal_subledger import SimulatedReversalLedger
from team14_reconciliation_hold import reconcile_review_statements


class BQA128IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.ledger = SimulatedReversalLedger()
        self.ledger.record(
            tx_id="tx1", evidence_id="pay1", gross_krw=1000,
            teacher_krw=700, platform_krw=200, referral_krw=30,
            benefit_krw=70)
        self.payments = [dict(tx_id="tx1", evidence_id="pay1", amount_krw=1000)]
        self.refunds = []
        self.payouts = [dict(tx_id="tx1", teacher_net_krw=700)]

    def tearDown(self):
        self.ledger.close()

    def check(self, **kwargs):
        return reconcile_review_statements(
            ledger=self.ledger,
            payments=kwargs.get("payments", self.payments),
            refunds=kwargs.get("refunds", self.refunds),
            payouts=kwargs.get("payouts", self.payouts))

    def assert_no_release(self, result):
        self.assertIs(result["payout_hold"], True)
        for key in ("payout_authorized", "real_money_enabled",
                    "provider_provenance_verified", "operator_approval_verified",
                    "operating_db_connected", "external_api_called"):
            self.assertIs(result[key], False, key)

    def add_corrupt_reversal(self, reversal_id, tx_id, refund, buckets):
        self.ledger.db.execute("PRAGMA foreign_keys=OFF")
        try:
            self.ledger.db.execute(
                "INSERT INTO sim_reversal VALUES(?,?,?,?,?,?)",
                (reversal_id, tx_id, "ref_evidence", "partial_refund",
                 refund, "untrusted"))
            for bucket, amount in buckets.items():
                self.ledger.db.execute(
                    "INSERT INTO sim_reversal_entry VALUES(?,?,?)",
                    (reversal_id, bucket, amount))
        finally:
            self.ledger.db.execute("PRAGMA foreign_keys=ON")

    def test_01_clean_match_is_review_only_and_payout_stays_held(self):
        result = self.check()
        self.assertEqual("MATCHED_REVIEW_ONLY", result["status"])
        self.assertEqual([], result["discrepancies"])
        self.assert_no_release(result)

    def test_02_valid_partial_refund_is_review_only_and_held(self):
        self.ledger.reverse(
            reversal_id="r1", tx_id="tx1", evidence_id="refund1",
            event_kind="partial_refund", refund_krw=100)
        teacher_refund = next(
            x["amount_krw"] for x in self.ledger.read_reversal("r1")["reversed_entries"]
            if x["bucket"] == "teacher")
        result = self.check(
            refunds=[dict(reversal_id="r1", tx_id="tx1",
                          evidence_id="refund1", amount_krw=100)],
            payouts=[dict(tx_id="tx1", teacher_net_krw=700-teacher_refund)])
        self.assertEqual("MATCHED_REVIEW_ONLY", result["status"])
        self.assert_no_release(result)

    def test_03_incomplete_four_bucket_reversal_must_hold(self):
        self.add_corrupt_reversal("r_missing", "tx1", 100, {"teacher": 100})
        result = self.check(
            refunds=[dict(reversal_id="r_missing", tx_id="tx1",
                          evidence_id="ref_evidence", amount_krw=100)],
            payouts=[dict(tx_id="tx1", teacher_net_krw=600)])
        self.assertIn("REVERSAL_ENTRY_MISMATCH:r_missing", result["discrepancies"])
        self.assertEqual("DISCREPANCY_HOLD", result["status"])
        self.assert_no_release(result)

    def test_04_four_bucket_wrong_refund_sum_must_hold(self):
        self.add_corrupt_reversal(
            "r_wrong", "tx1", 100,
            {"teacher": 90, "platform": 0, "referral": 0, "benefit": 0})
        result = self.check(
            refunds=[dict(reversal_id="r_wrong", tx_id="tx1",
                          evidence_id="ref_evidence", amount_krw=100)],
            payouts=[dict(tx_id="tx1", teacher_net_krw=610)])
        self.assertIn("REVERSAL_ENTRY_MISMATCH:r_wrong", result["discrepancies"])
        self.assert_no_release(result)

    def test_05_orphan_reversal_unknown_transaction_must_hold(self):
        # Simulate imported/corrupted SQLite evidence bypassing foreign-key enforcement.
        # All four buckets and matching caller-supplied refund exist, yet tx is absent.
        self.add_corrupt_reversal(
            "r_orphan", "tx_absent", 100,
            {"teacher": 70, "platform": 20, "referral": 3, "benefit": 7})
        result = self.check(
            refunds=[dict(reversal_id="r_orphan", tx_id="tx_absent",
                          evidence_id="ref_evidence", amount_krw=100)])
        self.assertEqual("DISCREPANCY_HOLD", result["status"],
                         "orphan reversal must not yield MATCHED_REVIEW_ONLY")
        self.assert_no_release(result)

    def test_06_orphan_reversal_entry_without_parent_must_hold(self):
        # A raw orphan bucket row must not be invisible to a ledger-integrity review.
        self.ledger.db.execute("PRAGMA foreign_keys=OFF")
        try:
            self.ledger.db.execute(
                "INSERT INTO sim_reversal_entry VALUES(?,?,?)",
                ("r_nonexistent", "teacher", 1))
        finally:
            self.ledger.db.execute("PRAGMA foreign_keys=ON")
        result = self.check()
        self.assertEqual("DISCREPANCY_HOLD", result["status"],
                         "orphan reversal bucket must not be ignored")
        self.assert_no_release(result)

    def test_07_unknown_refund_statement_holds(self):
        result = self.check(refunds=[
            dict(reversal_id="r_unknown", tx_id="tx1",
                 evidence_id="refund1", amount_krw=10)])
        self.assertIn("UNKNOWN_REFUND:r_unknown", result["discrepancies"])
        self.assert_no_release(result)

    def test_08_duplicate_payment_statement_rejected(self):
        with self.assertRaises(ValueError):
            self.check(payments=self.payments * 2)

    def test_09_invalid_id_types_rejected_before_sql(self):
        for bad in (None, [], {}, True, 1, "../escape"):
            with self.subTest(bad=repr(bad)), self.assertRaises(ValueError):
                self.check(refunds=[
                    dict(reversal_id=bad, tx_id="tx1",
                         evidence_id="refund1", amount_krw=1)])

    def test_10_overlong_statement_list_rejected(self):
        with self.assertRaises(ValueError):
            self.check(refunds=[
                dict(reversal_id="r" + str(i), tx_id="tx1",
                     evidence_id="ref", amount_krw=1)
                for i in range(1001)])

    def test_11_read_only_review_does_not_change_ledger_rows(self):
        tables = ("sim_tx", "sim_entry", "sim_reversal", "sim_reversal_entry")
        before = [self.ledger.db.execute(
            "SELECT COUNT(*) FROM " + table).fetchone()[0] for table in tables]
        self.check()
        after = [self.ledger.db.execute(
            "SELECT COUNT(*) FROM " + table).fetchone()[0] for table in tables]
        self.assertEqual(before, after)

    def test_12_missing_payout_statement_holds(self):
        result = self.check(payouts=[])
        self.assertIn("MISSING_PAYOUT_STATEMENT:tx1", result["discrepancies"])
        self.assert_no_release(result)


if __name__ == "__main__":
    unittest.main()
