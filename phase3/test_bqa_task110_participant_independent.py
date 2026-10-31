"""B/15 independent QA for #110 follow-up product SHA c6a746beaf68b193e2e4a7cd99172844397069ca.
Only mock signed policy, in-memory projections and HTML; no external services or money.
"""
import hashlib
import hmac
import unittest

from team14_referral_policy_preview import (
    canonical_policy_bytes, simulate_versioned_reward,
)
from team14_referral_participant_view import (
    ROLES, project_participant_view, render_participant_html,
)

ROSTER = {
    "learner": "learner_B110", "teacher": "teacher_B110",
    "referrer": "referrer_B110", "platform": "platform_B110",
}
KEY = b"B-independent-policy-fixture-32-bytes-minimum-2026"


def signed_candidate():
    policy = {
        "version": "bqa-fixture-v1", "rate_bps": 500,
        "cap_krw": 10000, "effective_from": 1, "expires_at": 2000,
        "refund_window_seconds": 0, "approved_by": "bqa_fixture",
        "scope": "referral_simulation_only",
    }
    signature = hmac.new(KEY, canonical_policy_bytes(policy), hashlib.sha256).hexdigest()
    return simulate_versioned_reward(
        policy_version=policy["version"], policy_record=policy,
        approval_signature=signature, trusted_verification_key=KEY,
        gross_krw=20000, payment_verified=True, lesson_completed=True,
        attendance_verified=True, refunded=False, referrer_eligible=True,
        paid_at=100, completed_at=200, as_of=1000,
    )


def project(role="referrer", simulation=None, **overrides):
    args = {
        "simulation": signed_candidate() if simulation is None else simulation,
        "role": role, "authenticated_actor_id": ROSTER[role],
        "trusted_roster": dict(ROSTER), "booking_evidence_verified": True,
    }
    args.update(overrides)
    return project_participant_view(**args)


class IndependentParticipantProjectionQA(unittest.TestCase):
    def test_01_valid_signed_mock_candidate_visible_to_referrer_only(self):
        for role in ROLES:
            with self.subTest(role=role):
                v = project(role)
                self.assertEqual("SIMULATED_CANDIDATE", v["state"])
                self.assertEqual(1000 if role == "referrer" else None,
                                 v["hypothetical_candidate_krw"])
                self.assertTrue(v["nonbinding"])
                self.assertFalse(v["live_payment_enabled"])
                self.assertFalse(v["live_payout_enabled"])
                self.assertFalse(v["operating_db_connected"])
                self.assertFalse(v["production_policy_activated"])

    def test_02_cross_role_actor_cannot_switch_identity(self):
        for role in ROLES:
            for other in ROLES:
                if role == other:
                    continue
                with self.subTest(role=role, other=other):
                    with self.assertRaises(PermissionError):
                        project(role, authenticated_actor_id=ROSTER[other])

    def test_03_roster_forgery_duplicate_and_missing_actor_fail_closed(self):
        variants = [
            {**ROSTER, "teacher": ROSTER["learner"]},
            {**ROSTER, "platform": "../spoof"},
            {k: v for k, v in ROSTER.items() if k != "teacher"},
            {**ROSTER, "auditor": "attacker"},
            {**ROSTER, "teacher": True},
        ]
        for roster in variants:
            with self.subTest(roster=roster):
                with self.assertRaises(ValueError):
                    project(trusted_roster=roster)

    def test_04_invalid_principal_type_and_path_fail_closed(self):
        for actor in ("", "../referrer_B110", "referrer B110", 5, True, None):
            with self.subTest(actor=actor):
                with self.assertRaises((ValueError, PermissionError)):
                    project(authenticated_actor_id=actor)

    def test_05_booking_evidence_missing_suppresses_valid_signed_candidate(self):
        v = project(booking_evidence_verified=False)
        self.assertEqual("BOOKING_UNVERIFIED", v["state"])
        self.assertIsNone(v["hypothetical_candidate_krw"])
        for value in (None, 0, 1, "true"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    project(booking_evidence_verified=value)

    def test_06_forged_unsigned_candidate_flag_suppresses_amount(self):
        s = signed_candidate()
        s["approval_evidence_verified"] = False
        v = project(simulation=s)
        self.assertEqual("POLICY_UNVERIFIED", v["state"])
        self.assertIsNone(v["hypothetical_candidate_krw"])

    def test_07_no_simulation_can_activate_money_or_points(self):
        for flag in ("real_money", "payment_enabled", "points_credited",
                     "payout_authorized", "production_policy_activated"):
            s = signed_candidate()
            s[flag] = True
            with self.subTest(flag=flag):
                with self.assertRaises(ValueError):
                    project(simulation=s)

    def test_08_missing_safety_field_and_malformed_amount_fail_closed(self):
        for field in ("payment_enabled", "policy_version",
                      "hypothetical_referral_candidate_krw"):
            s = signed_candidate()
            del s[field]
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    project(simulation=s)
        for amount in (-1, True, "1000", 10**13):
            s = signed_candidate()
            s["hypothetical_referral_candidate_krw"] = amount
            with self.subTest(amount=amount):
                with self.assertRaises(ValueError):
                    project(simulation=s)

    def test_09_non_candidate_state_must_not_carry_reward(self):
        s = signed_candidate()
        s["state"] = "WAIT_REFUND_WINDOW"
        with self.assertRaises(ValueError):
            project(simulation=s)

    def test_10_renderer_cannot_leak_amount_to_learner_or_teacher(self):
        for role in ("learner", "teacher", "platform"):
            v = project(role)
            v["hypothetical_candidate_krw"] = 1000
            with self.subTest(role=role):
                with self.assertRaises(ValueError):
                    render_participant_html(v)

    def test_11_renderer_escapes_all_untrusted_display_strings(self):
        v = project()
        payload = '<script>alert("BQA")</script>'
        v["reason"] = payload
        v["participant_explanation"] = payload
        v["cancellation_conditions"] = [payload]
        page = render_participant_html(v)
        self.assertNotIn(payload, page)
        self.assertNotIn("<script>", page)
        self.assertGreaterEqual(page.count("&lt;script&gt;"), 3)
        self.assertIn("Content-Security-Policy", page)
        self.assertNotIn("<form", page)
        self.assertNotIn("fetch(", page)

    def test_12_renderer_rejects_activation_and_non_referrer_money(self):
        for flag in ("live_payment_enabled", "live_payout_enabled",
                     "operating_db_connected", "production_policy_activated"):
            v = project()
            v[flag] = True
            with self.subTest(flag=flag):
                with self.assertRaises(ValueError):
                    render_participant_html(v)
        v = project("learner")
        v["hypothetical_candidate_krw"] = 1
        with self.assertRaises(ValueError):
            render_participant_html(v)


if __name__ == "__main__":
    unittest.main()
