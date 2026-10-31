"""#129 document bundle: isolated safety and role-boundary regressions."""
import unittest

from team14_document_bundle_preview import build_document_bundle, view_for_role


def row(identity, amount, state="succeeded"):
    return {"id": identity, "booking_id": "booking129",
            "amount_krw": amount, "state": state}


def ledger(identity, kind, amount):
    return {"id": identity, "booking_id": "booking129",
            "kind": kind, "amount_krw": amount}


def bundle(**overrides):
    args = {
        "booking_id": "booking129",
        "learner_id": "learner129",
        "teacher_id": "teacher129",
        "country_code": "KR",
        "payments": [row("p1", 1000)],
        "refunds": [row("r1", 100)],
        "payouts": [row("o1", 400, "paid")],
        "ledger": [
            ledger("lp", "payment", 1000),
            ledger("lr", "refund", -100),
            ledger("lo", "payout", -400),
        ],
        "platform_fee_krw": 150,
        "referral_fee_krw": 50,
        "trusted_evidence_verified": True,
        "policy_approved": True,
    }
    args.update(overrides)
    return build_document_bundle(**args)


class Task129DocumentBundleTests(unittest.TestCase):
    def test_all_four_document_structures_and_amounts(self):
        result = bundle()
        self.assertEqual("PREVIEW_ONLY", result["status"])
        self.assertEqual(4, len(result["documents"]))
        self.assertEqual(900, result["documents"]["transaction_statement"]["net_receipts_krw"])
        teacher = result["documents"]["teacher_settlement"]
        self.assertEqual(700, teacher["teacher_due_krw"])
        self.assertEqual(400, teacher["already_disbursed_krw"])
        self.assertEqual(300, teacher["remaining_due_krw"])

    def test_no_real_money_or_issuance_or_tax(self):
        result = bundle()
        for key in ("provider_connected", "operating_db_connected",
                    "official_document_issued", "real_payment_enabled",
                    "real_payout_enabled", "tax_filing_enabled"):
            self.assertIs(result[key], False)
        self.assertEqual("NOT_A_TAX_CERTIFICATE",
                         result["documents"]["income_support_data"]["status"])
        self.assertIsNone(result["documents"]["income_support_data"]["withholding_krw"])
        self.assertIsNone(result["documents"]["receipt_preview"]["provider_receipt_reference"])

    def test_missing_policy_holds(self):
        result = bundle(policy_approved=False)
        self.assertEqual("HOLD", result["status"])
        self.assertIn("APPROVED_POLICY_MISSING", result["reasons"])

    def test_missing_trusted_evidence_holds(self):
        result = bundle(trusted_evidence_verified=False)
        self.assertEqual("HOLD", result["status"])
        self.assertIn("TRUSTED_EVIDENCE_MISSING", result["reasons"])

    def test_ledger_mismatch_holds(self):
        result = bundle(payments=[row("p1", 999)])
        self.assertIn("PAYMENT_LEDGER_MISMATCH", result["reasons"])

    def test_refund_over_payment_holds(self):
        result = bundle(refunds=[row("r1", 1001)])
        self.assertIn("REFUND_EXCEEDS_PAYMENT", result["reasons"])

    def test_fees_over_net_hold(self):
        result = bundle(platform_fee_krw=800, referral_fee_krw=200)
        self.assertEqual("HOLD", result["status"])
        self.assertIn("FEES_EXCEED_NET_RECEIPTS", result["reasons"])

    def test_payout_over_teacher_due_holds(self):
        result = bundle(platform_fee_krw=400, referral_fee_krw=200)
        self.assertIn("TEACHER_PAYOUT_EXCEEDS_DUE", result["reasons"])

    def test_invalid_fee_amounts_fail_closed(self):
        for value in (True, False, 1.0, -1, "100", None, 10 ** 13):
            with self.subTest(value=value), self.assertRaises(ValueError):
                bundle(platform_fee_krw=value)
            with self.subTest(referral=value), self.assertRaises(ValueError):
                bundle(referral_fee_krw=value)

    def test_invalid_actor_ids_rejected(self):
        for value in ("", "../teacher", "x" * 65, None, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                bundle(teacher_id=value)
        with self.assertRaises(ValueError):
            bundle(teacher_id="learner129")

    def test_country_code_strict_but_no_tax_claim(self):
        for value in ("kr", "KOR", "", 123, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                bundle(country_code=value)
        self.assertEqual("KR", bundle()["documents"]["income_support_data"]["country_code"])

    def test_learner_receives_no_teacher_financial_documents(self):
        view = view_for_role(bundle(), actor_id="learner129", role="learner")
        self.assertEqual({"transaction_statement", "receipt_preview"},
                         set(view["documents"]))
        self.assertNotIn("teacher_id", str(view))

    def test_teacher_receives_no_learner_receipt(self):
        view = view_for_role(bundle(), actor_id="teacher129", role="teacher")
        self.assertEqual({"teacher_settlement", "income_support_data"},
                         set(view["documents"]))
        self.assertNotIn("learner_id", str(view))

    def test_role_and_actor_forgery_denied(self):
        for actor, role in (("stranger", "teacher"),
                            ("learner129", "teacher"),
                            ("teacher129", "learner"),
                            ("learner129", "admin"),
                            ("teacher129", "ADMIN")):
            with self.subTest(actor=actor, role=role), self.assertRaises(PermissionError):
                view_for_role(bundle(), actor_id=actor, role=role)

    def test_bad_view_input_denied(self):
        with self.assertRaises(ValueError):
            view_for_role(bundle(), actor_id=True, role="teacher")
        with self.assertRaises(ValueError):
            view_for_role({"teacher_id": "teacher129"}, actor_id="teacher129", role="teacher")

    def test_view_is_defensive_copy(self):
        original = bundle()
        view = view_for_role(original, actor_id="teacher129", role="teacher")
        view["documents"]["teacher_settlement"]["teacher_due_krw"] = 1
        self.assertEqual(700, original["documents"]["teacher_settlement"]["teacher_due_krw"])

    def test_deterministic_ids_no_time_or_secret(self):
        a, b = bundle(), bundle()
        self.assertEqual(a, b)
        for value in a["documents"].values():
            self.assertTrue(value["document_id"].startswith("preview_"))
            self.assertNotIn("password", str(value).lower())
            self.assertNotIn("cvv", str(value).lower())

    def test_pending_payout_hold(self):
        result = bundle(
            payouts=[row("o1", 400, "pending")],
            ledger=[ledger("lp", "payment", 1000),
                    ledger("lr", "refund", -100)])
        self.assertIn("PENDING_PAYOUT_REVIEW_REQUIRED", result["reasons"])

    def test_zero_amounts_do_not_issue_receipt(self):
        result = bundle(
            payments=[], refunds=[], payouts=[], ledger=[],
            platform_fee_krw=0, referral_fee_krw=0)
        self.assertEqual(0, result["documents"]["receipt_preview"]["gross_krw"])
        self.assertEqual("NOT_A_FISCAL_OR_PROVIDER_RECEIPT",
                         result["documents"]["receipt_preview"]["status"])


if __name__ == "__main__":
    unittest.main()
