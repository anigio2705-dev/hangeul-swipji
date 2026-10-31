"""B/15 independent #129 exact-SHA adversarial QA, mock-only, no issuance."""
from copy import deepcopy
from unittest.mock import patch
import unittest

from team14_document_bundle_preview import build_document_bundle, view_for_role


def payment(identifier, amount, booking="b129"):
    return {"id": identifier, "booking_id": booking, "amount_krw": amount, "state": "succeeded"}


def payout(identifier, amount, state="paid"):
    return {"id": identifier, "booking_id": "b129", "amount_krw": amount, "state": state}


def entry(identifier, kind, amount):
    return {"id": identifier, "booking_id": "b129", "kind": kind, "amount_krw": amount}


def make(**changes):
    args = dict(
        booking_id="b129", learner_id="learner_X", teacher_id="teacher_Y",
        country_code="KR",
        payments=[payment("pay_A", 600), payment("pay_B", 400)],
        refunds=[payment("refund_A", 250)],
        ledger=[entry("l1", "payment", 600), entry("l2", "payment", 400),
                entry("l3", "refund", -250), entry("l4", "payout", -300)],
        payouts=[payout("out_A", 300)],
        platform_fee_krw=100, referral_fee_krw=50,
        trusted_evidence_verified=True, policy_approved=True,
    )
    args.update(changes)
    return build_document_bundle(**args)


class BQA129Documents(unittest.TestCase):
    def test_01_split_payment_refund_fee_conservation(self):
        data = make()
        self.assertEqual(data["status"], "PREVIEW_ONLY")
        teacher = data["documents"]["teacher_settlement"]
        self.assertEqual((750, 600, 300, 300),
                         (teacher["net_receipts_krw"], teacher["teacher_due_krw"],
                          teacher["already_disbursed_krw"], teacher["remaining_due_krw"]))
        self.assertEqual(750, data["documents"]["receipt_preview"]["net_receipts_krw"])

    def test_02_cross_booking_evidence_is_hold(self):
        data = make(payments=[payment("pay_A", 600, "other"),
                              payment("pay_B", 400)])
        self.assertEqual(data["status"], "HOLD")
        self.assertIn("payment_FOREIGN_BOOKING", data["reasons"])

    def test_03_missing_policy_and_evidence_cannot_look_ready(self):
        data = make(trusted_evidence_verified=False, policy_approved=False)
        self.assertEqual(data["status"], "HOLD")
        self.assertIn("TRUSTED_EVIDENCE_MISSING", data["reasons"])
        self.assertIn("APPROVED_POLICY_MISSING", data["reasons"])

    def test_04_verification_flags_are_strict_booleans(self):
        for value in (1, 0, "true", [], None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                make(trusted_evidence_verified=value)
            with self.subTest(policy=value), self.assertRaises(ValueError):
                make(policy_approved=value)

    def test_05_learner_view_does_not_leak_teacher_financials(self):
        result = view_for_role(make(), actor_id="learner_X", role="learner")
        self.assertEqual(set(result["documents"]),
                         {"transaction_statement", "receipt_preview"})
        self.assertNotIn("teacher_Y", str(result))
        self.assertNotIn("teacher_due_krw", str(result))

    def test_06_teacher_view_does_not_leak_learner_receipt(self):
        result = view_for_role(make(), actor_id="teacher_Y", role="teacher")
        self.assertEqual(set(result["documents"]),
                         {"teacher_settlement", "income_support_data"})
        self.assertNotIn("learner_X", str(result))
        self.assertNotIn("provider_receipt_reference", str(result))

    def test_07_actor_role_confusion_denied(self):
        for actor, role in (("learner_X", "teacher"), ("teacher_Y", "learner"),
                            ("stranger", "learner"), ("teacher_Y", "admin")):
            with self.subTest(actor=actor, role=role), self.assertRaises(PermissionError):
                view_for_role(make(), actor_id=actor, role=role)

    def test_08_invalid_actor_and_country_fail_closed(self):
        for actor in ("../bad", "bad/id", "", "x" * 65, True):
            with self.subTest(actor=actor), self.assertRaises(ValueError):
                make(teacher_id=actor)
        for country in ("kr", "KOR", "K1", "", None):
            with self.subTest(country=country), self.assertRaises(ValueError):
                make(country_code=country)

    def test_09_country_change_changes_income_document_id(self):
        kr = make(country_code="KR")["documents"]["income_support_data"]["document_id"]
        us = make(country_code="US")["documents"]["income_support_data"]["document_id"]
        self.assertNotEqual(kr, us)

    def test_10_refund_all_with_positive_fees_holds(self):
        data = make(refunds=[payment("refund_A", 1000)],
                    ledger=[entry("l1", "payment", 600), entry("l2", "payment", 400),
                            entry("l3", "refund", -1000)],
                    payouts=[], platform_fee_krw=1, referral_fee_krw=1)
        self.assertEqual(data["status"], "HOLD")
        self.assertIn("FEES_EXCEED_NET_RECEIPTS", data["reasons"])

    def test_11_overdisbursement_holds(self):
        data = make(platform_fee_krw=300, referral_fee_krw=200)
        self.assertEqual(data["status"], "HOLD")
        self.assertIn("TEACHER_PAYOUT_EXCEEDS_DUE", data["reasons"])

    def test_12_no_official_issuance_even_with_approved_mock_flags(self):
        data = make()
        for key in ("provider_connected", "operating_db_connected",
                    "official_document_issued", "real_payment_enabled",
                    "real_payout_enabled", "tax_filing_enabled"):
            self.assertIs(data[key], False)
        self.assertIsNone(data["documents"]["income_support_data"]["withholding_krw"])
        self.assertIsNone(data["documents"]["receipt_preview"]["provider_receipt_reference"])

    def test_13_input_immutability_and_view_copy(self):
        p = [payment("pay_A", 600), payment("pay_B", 400)]
        before = deepcopy(p)
        data = make(payments=p)
        self.assertEqual(p, before)
        teacher = view_for_role(data, actor_id="teacher_Y", role="teacher")
        teacher["documents"]["teacher_settlement"]["teacher_due_krw"] = -999
        self.assertEqual(600, data["documents"]["teacher_settlement"]["teacher_due_krw"])

    def test_14_no_external_io_during_document_preview(self):
        with patch("sqlite3.connect", side_effect=AssertionError("DB IO forbidden")), \
             patch("urllib.request.urlopen", side_effect=AssertionError("HTTP forbidden")):
            data = make()
            self.assertEqual(data["status"], "PREVIEW_ONLY")

    def test_15_permuting_same_evidence_keeps_stable_preview_ids(self):
        original = make()
        reordered = make(payments=[payment("pay_B", 400), payment("pay_A", 600)],
                         ledger=[entry("l4", "payout", -300), entry("l3", "refund", -250),
                                 entry("l2", "payment", 400), entry("l1", "payment", 600)])
        self.assertEqual(
            {k: v["document_id"] for k, v in original["documents"].items()},
            {k: v["document_id"] for k, v in reordered["documents"].items()})


if __name__ == "__main__":
    unittest.main()
