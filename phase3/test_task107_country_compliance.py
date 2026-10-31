"""#107 fail-closed country review checks; no external payment or database."""
import unittest
from pathlib import Path

from team14_country_compliance import evaluate_country_referral, COUNTRIES


def evaluate(**changes):
    args = dict(country_code="KR", reward_kind="discount",
                referral_depth=1, as_of=1000)
    args.update(changes)
    return evaluate_country_referral(**args)


def complete_evidence(**changes):
    record = dict(country_code="KR", legal_reviewed=True, tax_reviewed=True,
                  reviewed_at=500, expires_at=1500, max_referral_depth=2,
                  reviewed_reward_kinds=["discount", "points"],
                  review_reference="REVIEW-TEST-001", policy_version="draft-v1")
    record.update(changes)
    return record


class CountryComplianceReviewTests(unittest.TestCase):
    def assert_never_live(self, result):
        for field in ("policy_approved", "real_money", "payment_enabled",
                      "cash_payout_enabled", "can_activate"):
            self.assertIs(result[field], False, field)
        self.assertIs(result["owner_approval_required"], True)

    def test_every_target_country_denied_by_default(self):
        for code in COUNTRIES:
            with self.subTest(code=code):
                result = evaluate(country_code=code)
                self.assertEqual(result["status"], "LEGAL_TAX_REVIEW_REQUIRED")
                self.assert_never_live(result)

    def test_unsupported_country_denied(self):
        result = evaluate(country_code="ZZ")
        self.assertEqual(result["status"], "UNSUPPORTED_COUNTRY")
        self.assert_never_live(result)

    def test_complete_untrusted_evidence_does_not_authorize(self):
        result = evaluate(review_evidence=complete_evidence())
        self.assertTrue(result["review_evidence_complete_unverified"])
        self.assertEqual(result["status"], "EVIDENCE_UNVERIFIED_OWNER_DECISION_REQUIRED")
        self.assert_never_live(result)

    def test_wrong_country_evidence_rejected(self):
        result = evaluate(review_evidence=complete_evidence(country_code="US"))
        self.assertFalse(result["review_evidence_complete_unverified"])
        self.assert_never_live(result)

    def test_future_or_expired_review_rejected(self):
        for record in (complete_evidence(reviewed_at=1001),
                       complete_evidence(expires_at=1000)):
            with self.subTest(record=record):
                self.assertFalse(evaluate(review_evidence=record)["review_evidence_complete_unverified"])

    def test_missing_legal_or_tax_review_rejected(self):
        for record in (complete_evidence(legal_reviewed=False),
                       complete_evidence(tax_reviewed=False),
                       complete_evidence(legal_reviewed=1)):
            self.assertFalse(evaluate(review_evidence=record)["review_evidence_complete_unverified"])

    def test_depth_and_reward_scope_enforced(self):
        self.assertFalse(evaluate(referral_depth=3, review_evidence=complete_evidence())[
            "review_evidence_complete_unverified"])
        self.assertFalse(evaluate(reward_kind="cash_payout",
                                  review_evidence=complete_evidence())[
            "review_evidence_complete_unverified"])

    def test_multilevel_and_cash_risk_flags(self):
        result = evaluate(reward_kind="cash_payout", referral_depth=3,
                          review_evidence=complete_evidence(
                              max_referral_depth=3,
                              reviewed_reward_kinds=["cash_payout"]))
        self.assertIn("MULTI_LEVEL_REWARD_RISK", result["warnings"])
        self.assertIn("CASH_EQUIVALENT_OR_PAYOUT_RISK", result["warnings"])
        self.assert_never_live(result)

    def test_forged_complete_record_never_approves(self):
        record = complete_evidence(policy_approved=True, payment_enabled=True,
                                   cash_payout_enabled=True, real_money=True)
        self.assert_never_live(evaluate(review_evidence=record))

    def test_reject_bad_inputs(self):
        for args in (dict(country_code="kr"), dict(country_code="KOR"),
                     dict(country_code=None), dict(reward_kind=[]),
                     dict(reward_kind="live_transfer"), dict(referral_depth=True),
                     dict(referral_depth=0), dict(referral_depth=11),
                     dict(as_of=-1), dict(as_of=True),
                     dict(review_evidence="approved")):
            with self.subTest(args=args), self.assertRaises(ValueError):
                evaluate(**args)

    def test_html_preview_has_no_payment_action(self):
        html = Path(__file__).with_name("referral-compliance-review.html").read_text(encoding="utf-8")
        self.assertIn('id="payout" type="button" disabled', html)
        self.assertIn("법률·세무 검토 전", html)
        self.assertNotIn("fetch(", html)
        self.assertNotIn(".disabled = false", html)
        shell = Path(__file__).with_name("shell.html").read_text(encoding="utf-8")
        self.assertIn('href="/phase3/referral-compliance-review.html"', shell)


if __name__ == "__main__":
    unittest.main()
