"""#128 isolated reconciliation: no provider, operating DB or money."""
import unittest

from team14_reconciliation_review import reconcile_booking


def row(record_id, amount, state="succeeded", booking="book_128"):
    return {"id": record_id, "booking_id": booking,
            "amount_krw": amount, "state": state}


def ledger(record_id, kind, amount, booking="book_128"):
    return {"id": record_id, "booking_id": booking,
            "kind": kind, "amount_krw": amount}


def review(**changes):
    args = {
        "booking_id": "book_128",
        "payments": [row("pay_1", 1000)],
        "refunds": [row("refund_1", 100)],
        "payouts": [row("payout_1", 400, "paid")],
        "ledger": [
            ledger("l_pay", "payment", 1000),
            ledger("l_refund", "refund", -100),
            ledger("l_payout", "payout", -400),
        ],
        "trusted_evidence_verified": True,
        "policy_approved": True,
    }
    args.update(changes)
    return reconcile_booking(**args)


class Task128ReconciliationTests(unittest.TestCase):
    def test_matching_review_is_not_money_execution(self):
        v = review()
        self.assertEqual("MATCHED_REVIEW_ONLY", v["status"])
        self.assertFalse(v["payout_hold_required"])
        self.assertFalse(v["payout_execution_enabled"])
        self.assertFalse(v["real_payment_enabled"])
        self.assertFalse(v["operating_db_connected"])
        self.assertEqual(500, v["unsettled_krw"])

    def test_payment_mismatch_holds(self):
        v = review(payments=[row("pay_1", 999)])
        self.assertIn("PAYMENT_LEDGER_MISMATCH", v["reasons"])
        self.assertTrue(v["payout_hold_required"])

    def test_refund_mismatch_holds(self):
        v = review(refunds=[row("refund_1", 101)])
        self.assertIn("REFUND_LEDGER_MISMATCH", v["reasons"])

    def test_payout_mismatch_holds(self):
        v = review(payouts=[row("payout_1", 401, "paid")])
        self.assertIn("PAYOUT_LEDGER_MISMATCH", v["reasons"])

    def test_over_refund_holds(self):
        v = review(refunds=[row("refund_1", 1001)])
        self.assertIn("REFUND_EXCEEDS_PAYMENT", v["reasons"])

    def test_over_payout_holds(self):
        v = review(payouts=[row("payout_1", 901, "paid")])
        self.assertIn("PAYOUT_EXCEEDS_NET_RECEIPTS", v["reasons"])

    def test_duplicate_event_holds(self):
        v = review(payments=[row("pay_1", 500), row("pay_1", 500)])
        self.assertIn("payment_DUPLICATE_ID", v["reasons"])

    def test_duplicate_ledger_holds(self):
        v = review(ledger=[ledger("same", "payment", 1000),
                           ledger("same", "refund", -100),
                           ledger("other", "payout", -400)])
        self.assertIn("ledger_DUPLICATE_ID", v["reasons"])

    def test_cross_booking_evidence_holds(self):
        v = review(refunds=[row("refund_1", 100, booking="another")])
        self.assertIn("refund_FOREIGN_BOOKING", v["reasons"])

    def test_cross_booking_ledger_holds(self):
        v = review(ledger=[ledger("l_pay", "payment", 1000, booking="another"),
                           ledger("l_refund", "refund", -100),
                           ledger("l_payout", "payout", -400)])
        self.assertIn("ledger_FOREIGN_BOOKING", v["reasons"])

    def test_pending_and_failed_payouts_halt_review(self):
        for state, reason in (
            ("pending", "PENDING_PAYOUT_REVIEW_REQUIRED"),
            ("failed", "FAILED_PAYOUT_REVIEW_REQUIRED"),
        ):
            with self.subTest(state=state):
                v = review(payouts=[row("payout_1", 400, state)],
                           ledger=[ledger("l_pay", "payment", 1000),
                                   ledger("l_refund", "refund", -100)])
                self.assertIn(reason, v["reasons"])

    def test_unverified_evidence_and_unapproved_policy_hold(self):
        v = review(trusted_evidence_verified=False, policy_approved=False)
        self.assertIn("TRUSTED_EVIDENCE_MISSING", v["reasons"])
        self.assertIn("APPROVED_POLICY_MISSING", v["reasons"])

    def test_invalid_amounts_rejected(self):
        for amount in (True, 1.0, -1, "100", 10**13):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                review(payments=[row("pay_1", amount)])

    def test_invalid_ledger_sign_and_types(self):
        v = review(ledger=[ledger("l_pay", "payment", -1000),
                           ledger("l_refund", "refund", -100),
                           ledger("l_payout", "payout", -400)])
        self.assertIn("ledger_INVALID_SIGN", v["reasons"])
        for amount in (True, 1.0, "100"):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                review(ledger=[ledger("l_pay", "payment", amount)])

    def test_schema_and_boolean_flags_fail_closed(self):
        with self.assertRaises(ValueError):
            review(payments=[{"id": "p", "booking_id": "book_128",
                              "amount_krw": 1000, "state": "succeeded",
                              "untrusted": True}])
        for value in (1, "true", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                review(policy_approved=value)

    def test_booking_identity_and_bounded_inputs(self):
        for booking in ("../escape", "", True, "x" * 65):
            with self.subTest(booking=booking), self.assertRaises(ValueError):
                review(booking_id=booking)
        with self.assertRaises(ValueError):
            review(payments=[row("x" + str(i), 1) for i in range(1001)])


if __name__ == "__main__":
    unittest.main()
