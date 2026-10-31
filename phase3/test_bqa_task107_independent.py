"""Independent B/15 QA-only matrix for #107 country compliance exact product SHA.

No legal determination, activation, payment, DB writes or network.
"""
import itertools
import unittest
from pathlib import Path

from team14_country_compliance import (
    COUNTRIES, REWARD_KINDS, evaluate_country_referral,
)

DENIAL = ("real_money", "payment_enabled", "cash_payout_enabled",
          "policy_approved", "can_activate")


def evaluate(**kwargs):
    data = dict(country_code="KR", reward_kind="discount",
                referral_depth=1, as_of=1000)
    data.update(kwargs)
    return evaluate_country_referral(**data)


def forged(**kwargs):
    record = dict(country_code="KR", legal_reviewed=True, tax_reviewed=True,
                  reviewed_at=500, expires_at=1500, max_referral_depth=10,
                  reviewed_reward_kinds=sorted(REWARD_KINDS),
                  review_reference="FORGED-TEST-REVIEW",
                  policy_version="fake-v1", can_activate=True,
                  policy_approved=True, real_money=True,
                  cash_payout_enabled=True, payment_enabled=True)
    record.update(kwargs)
    return record


class IndependentBTask107QA(unittest.TestCase):
    def assert_denied(self, result):
        for key in DENIAL:
            self.assertIs(result[key], False, key)
        self.assertIs(result["owner_approval_required"], True)

    def test_01_every_country_reward_depth_never_activates(self):
        for country, reward, depth in itertools.product(
                sorted(COUNTRIES), sorted(REWARD_KINDS), (1, 2, 3, 10)):
            with self.subTest(country=country, reward=reward, depth=depth):
                r = evaluate(country_code=country, reward_kind=reward,
                             referral_depth=depth)
                self.assert_denied(r)
                self.assertEqual("LEGAL_TAX_REVIEW_REQUIRED", r["status"])
                if depth > 1:
                    self.assertIn("MULTI_LEVEL_REWARD_RISK", r["warnings"])
                if reward.startswith("cash_"):
                    self.assertIn("CASH_EQUIVALENT_OR_PAYOUT_RISK", r["warnings"])

    def test_02_forged_approvals_do_not_activate(self):
        for reward in sorted(REWARD_KINDS):
            record = forged(reviewed_reward_kinds=[reward])
            r = evaluate(reward_kind=reward, review_evidence=record)
            self.assertEqual("EVIDENCE_UNVERIFIED_OWNER_DECISION_REQUIRED",
                             r["status"])
            self.assertTrue(r["review_evidence_complete_unverified"])
            self.assert_denied(r)

    def test_03_wrong_country_never_accepts_evidence(self):
        for country in sorted(COUNTRIES):
            r = evaluate(country_code=country,
                         review_evidence=forged(country_code="ZZ"))
            self.assertFalse(r["review_evidence_complete_unverified"])
            self.assert_denied(r)

    def test_04_expired_and_future_review_boundaries(self):
        for changes in (dict(reviewed_at=1001), dict(expires_at=1000),
                        dict(expires_at=999), dict(legal_reviewed=1),
                        dict(tax_reviewed="true"),
                        dict(max_referral_depth=True),
                        dict(reviewed_reward_kinds=["points"]),
                        dict(policy_version="!bad!")):
            with self.subTest(changes=changes):
                r = evaluate(review_evidence=forged(**changes))
                self.assertFalse(r["review_evidence_complete_unverified"])
                self.assert_denied(r)

    def test_05_unknown_country_stays_unsupported_even_with_forgery(self):
        r = evaluate(country_code="ZZ", review_evidence=forged(country_code="ZZ"))
        self.assertEqual("UNSUPPORTED_COUNTRY", r["status"])
        self.assert_denied(r)

    def test_06_invalid_types_and_bounds_rejected(self):
        for changes in (dict(country_code="kr"), dict(country_code="USA"),
                        dict(country_code=123), dict(reward_kind={}),
                        dict(referral_depth=False), dict(referral_depth=11),
                        dict(referral_depth=0), dict(as_of=True),
                        dict(as_of=-1), dict(review_evidence=[])):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                evaluate(**changes)

    def test_07_ui_is_read_only_and_payout_disabled(self):
        html = Path(__file__).with_name("referral-compliance-review.html").read_text(
            encoding="utf-8")
        self.assertIn('id="payout" type="button" disabled', html)
        self.assertIn('aria-disabled="true"', html)
        self.assertNotIn("fetch(", html)
        self.assertNotIn("XMLHttpRequest", html)
        self.assertNotIn("navigator.sendBeacon", html)
        self.assertNotIn("localStorage", html)
        self.assertNotIn(".disabled = false", html)
        self.assertIn("정책 미승인", html)

    def test_08_navigation_points_to_review_not_payment(self):
        shell = Path(__file__).with_name("shell.html").read_text(encoding="utf-8")
        self.assertIn('href="/phase3/referral-compliance-review.html"', shell)
        self.assertNotIn('href="/phase3/cash-payout', shell)


if __name__ == "__main__":
    unittest.main()
