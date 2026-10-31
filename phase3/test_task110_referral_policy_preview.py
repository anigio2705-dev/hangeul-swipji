"""#110 independent candidate unit tests; all policy signatures are test fixtures."""
import hashlib
import hmac
import unittest

from team14_referral_policy_preview import (
    canonical_policy_bytes, simulate_versioned_reward,
)

TEST_KEY = b"test-only-key-not-a-real-approval-00000000000000000"


def policy(**changes):
    p = dict(version="fixture-v1", rate_bps=300, cap_krw=50000,
             effective_from=100, expires_at=1000000,
             refund_window_seconds=7 * 86400,
             approved_by="test-only-approver", scope="referral_simulation_only")
    p.update(changes)
    return p


def signed(p):
    return hmac.new(TEST_KEY, canonical_policy_bytes(p), hashlib.sha256).hexdigest()


def scenario(**changes):
    p = policy()
    params = dict(policy_version=p["version"], policy_record=p,
                  approval_signature=signed(p), trusted_verification_key=TEST_KEY,
                  gross_krw=100000, payment_verified=True, lesson_completed=True,
                  attendance_verified=True, refunded=False, referrer_eligible=True,
                  risk_flags=[], paid_at=100, completed_at=200, as_of=700000)
    params.update(changes)
    return simulate_versioned_reward(**params)


class ReferralPolicyPreviewTests(unittest.TestCase):
    def assert_never_live(self, r):
        for k in ("real_money", "payment_enabled", "points_credited",
                  "payout_authorized", "production_policy_activated"):
            self.assertIs(r[k], False)

    def test_no_approval_evidence_is_blocked(self):
        r = scenario(policy_record=None, approval_signature=None)
        self.assertEqual("POLICY_UNVERIFIED", r["state"])
        self.assertEqual(0, r["hypothetical_referral_candidate_krw"])
        self.assert_never_live(r)

    def test_signed_fixture_simulation_only(self):
        r = scenario()
        self.assertTrue(r["approval_evidence_verified"])
        self.assertEqual("SIMULATED_CANDIDATE", r["state"])
        self.assertEqual(3000, r["hypothetical_referral_candidate_krw"])
        self.assert_never_live(r)

    def test_version_and_signature_tampering_fail_closed(self):
        p = policy(rate_bps=9999)
        for changes in ({"policy_version": "fixture-v2"},
                        {"policy_record": p},
                        {"approval_signature": "a" * 64},
                        {"trusted_verification_key": None},
                        {"trusted_verification_key": b"short"}):
            with self.subTest(changes=changes):
                r = scenario(**changes)
                self.assertEqual("POLICY_UNVERIFIED", r["state"])
                self.assert_never_live(r)

    def test_policy_not_effective_at_boundaries(self):
        self.assertEqual("POLICY_NOT_EFFECTIVE", scenario(as_of=99, payment_verified=False,
                         lesson_completed=False)["state"])
        self.assertEqual("POLICY_NOT_EFFECTIVE", scenario(as_of=1000000)["state"])

    def test_refund_void_even_after_window(self):
        r = scenario(refunded=True)
        self.assertEqual("REFUND_VOID", r["state"])
        self.assertEqual(0, r["hypothetical_referral_candidate_krw"])

    def test_risk_requires_review(self):
        r = scenario(risk_flags=["SELF_REFERRAL"])
        self.assertEqual("RISK_REVIEW", r["state"])
        self.assert_never_live(r)

    def test_referrer_ineligible_does_not_block_learning(self):
        r = scenario(referrer_eligible=False)
        self.assertEqual("REFERRER_INELIGIBLE", r["state"])
        self.assertIn("독립적", r["participants"]["learner"])

    def test_wait_payment(self):
        self.assertEqual("WAIT_PAYMENT", scenario(payment_verified=False, paid_at=None)["state"])

    def test_wait_lesson_or_attendance(self):
        self.assertEqual("WAIT_LESSON", scenario(lesson_completed=False, completed_at=None)["state"])
        self.assertEqual("WAIT_LESSON", scenario(attendance_verified=False)["state"])

    def test_refund_window_exact_boundary(self):
        self.assertEqual("WAIT_REFUND_WINDOW", scenario(as_of=604999)["state"])
        self.assertEqual("SIMULATED_CANDIDATE", scenario(as_of=605000)["state"])

    def test_cap_and_zero_rate(self):
        p = policy(rate_bps=10000, cap_krw=1000)
        self.assertEqual(1000, scenario(policy_record=p, approval_signature=signed(p))[
            "hypothetical_referral_candidate_krw"])
        p = policy(rate_bps=0)
        self.assertEqual(0, scenario(policy_record=p, approval_signature=signed(p))[
            "hypothetical_referral_candidate_krw"])

    def test_all_participants_have_explanations(self):
        r = scenario()
        self.assertEqual({"learner", "teacher", "referrer", "platform"}, set(r["participants"]))
        self.assertGreaterEqual(len(r["cancellation_conditions"]), 4)

    def test_boolean_and_negative_values_rejected(self):
        for changes in ({"gross_krw": True}, {"gross_krw": -1},
                        {"as_of": True}, {"payment_verified": 1},
                        {"referrer_eligible": "yes"}, {"risk_flags": "SELF_REFERRAL"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                scenario(**changes)

    def test_invalid_future_event_rejected(self):
        for changes in ({"paid_at": None}, {"completed_at": None},
                        {"paid_at": 800000}, {"completed_at": 800000}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                scenario(**changes)

    def test_invalid_policy_schema_rejected(self):
        for p in (policy(scope="real_money"), policy(rate_bps=True),
                  policy(rate_bps=10001), policy(expires_at=100),
                  {**policy(), "unapproved_field": 1}):
            with self.subTest(p=p), self.assertRaises(ValueError):
                scenario(policy_record=p)

    def test_read_only_ui_never_claims_approved_policy(self):
        from pathlib import Path
        html = Path(__file__).with_name("referral-policy-preview.html").read_text(encoding="utf-8")
        self.assertIn("POLICY_UNVERIFIED", html)
        self.assertIn("읽기 전용", html)
        self.assertIn("참여자별 설명", html)
        self.assertNotIn("fetch(", html)
        self.assertNotIn("<form", html)

    def test_no_database_or_payment_imports(self):
        import inspect
        import team14_referral_policy_preview as mod
        source = inspect.getsource(mod)
        for banned in ("import sqlite3", "import requests", "import stripe", "from server import"):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()
