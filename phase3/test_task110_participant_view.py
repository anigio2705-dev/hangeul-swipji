"""#110 follow-up: participant projection adversarial regressions (mock only)."""
import unittest

from team14_referral_policy_preview import simulate_versioned_reward
from team14_referral_participant_view import (
    ROLES, project_participant_view, render_participant_html,
)

ROSTER = {"learner": "student_110", "teacher": "teacher_110",
          "referrer": "referrer_110", "platform": "operator_110"}


def simulated(**updates):
    r = simulate_versioned_reward(
        policy_version="fixture-v1", gross_krw=100000,
        payment_verified=False, lesson_completed=False,
        attendance_verified=False, refunded=False, referrer_eligible=True,
        as_of=1000,
    )
    r.update(updates)
    return r


def view(role="referrer", **updates):
    kw = dict(simulation=simulated(), role=role,
              authenticated_actor_id=ROSTER[role],
              trusted_roster=ROSTER, booking_evidence_verified=True)
    kw.update(updates)
    return project_participant_view(**kw)


class ParticipantProjectionTests(unittest.TestCase):
    def test_each_role_has_separate_read_only_view(self):
        for role in ROLES:
            with self.subTest(role=role):
                v = view(role)
                self.assertEqual(role, v["role"])
                self.assertEqual("POLICY_UNVERIFIED", v["state"])
                self.assertIsNone(v["hypothetical_candidate_krw"])
                self.assertTrue(v["nonbinding"])
                self.assertFalse(v["live_payment_enabled"])
                self.assertFalse(v["live_payout_enabled"])

    def test_wrong_actor_cannot_view_other_role(self):
        for role in ROLES:
            with self.subTest(role=role), self.assertRaises(PermissionError):
                view(role, authenticated_actor_id="attacker")

    def test_role_switch_with_same_actor_fails(self):
        with self.assertRaises(PermissionError):
            view("teacher", authenticated_actor_id=ROSTER["learner"])

    def test_duplicate_roster_id_rejected(self):
        with self.assertRaises(ValueError):
            view(trusted_roster={**ROSTER, "teacher": ROSTER["learner"]})

    def test_missing_or_extra_roster_role_rejected(self):
        for roster in ({"learner": "student_110"},
                       {**ROSTER, "auditor": "auditor_110"}):
            with self.subTest(roster=roster), self.assertRaises(ValueError):
                view(trusted_roster=roster)

    def test_bad_identity_rejected(self):
        for bad in ("", "../root", "user name", "x" * 65, 123):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                view(trusted_roster={**ROSTER, "teacher": bad})

    def test_booking_evidence_false_blocks_candidate(self):
        v = view(booking_evidence_verified=False)
        self.assertEqual("BOOKING_UNVERIFIED", v["state"])
        self.assertIsNone(v["hypothetical_candidate_krw"])

    def test_booking_evidence_requires_strict_bool(self):
        with self.assertRaises(ValueError):
            view(booking_evidence_verified=1)

    def test_unsigned_policy_cannot_show_candidate_even_if_state_forged(self):
        v = view(simulation=simulated(
            state="SIMULATED_CANDIDATE",
            hypothetical_referral_candidate_krw=999,
            approval_evidence_verified=False))
        self.assertEqual("POLICY_UNVERIFIED", v["state"])
        self.assertIsNone(v["hypothetical_candidate_krw"])

    def test_mock_signed_candidate_visible_only_to_referrer(self):
        s = simulated(state="SIMULATED_CANDIDATE",
                      hypothetical_referral_candidate_krw=3000,
                      approval_evidence_verified=True)
        for role in ROLES:
            with self.subTest(role=role):
                v = view(role, simulation=s)
                self.assertEqual(3000 if role == "referrer" else None,
                                 v["hypothetical_candidate_krw"])

    def test_candidate_cannot_become_live_payment(self):
        for flag in ("real_money", "payment_enabled", "points_credited",
                     "payout_authorized", "production_policy_activated"):
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                view(simulation=simulated(**{flag: True}))

    def test_non_candidate_cannot_hold_positive_amount(self):
        with self.assertRaises(ValueError):
            view(simulation=simulated(hypothetical_referral_candidate_krw=1))

    def test_invalid_schema_or_money_rejected(self):
        for bad in (simulated(policy_version="<script>"),
                    simulated(hypothetical_referral_candidate_krw=True),
                    simulated(state="UNKNOWN"),
                    simulated(approval_evidence_verified="true"),
                    {"state": "SIMULATED_CANDIDATE"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                view(simulation=bad)

    def test_html_escapes_explanations(self):
        v = view()
        v["participant_explanation"] = '<img src=x onerror=alert(1)>'
        html = render_participant_html(v)
        self.assertNotIn("<img", html)
        self.assertIn("&lt;img", html)
        self.assertNotIn("fetch(", html)
        self.assertNotIn("<form", html)

    def test_renderer_refuses_cross_role_amount(self):
        v = view("learner")
        v["hypothetical_candidate_krw"] = 500
        with self.assertRaises(ValueError):
            render_participant_html(v)

    def test_renderer_refuses_activated_view(self):
        v = view()
        v["live_payout_enabled"] = True
        with self.assertRaises(ValueError):
            render_participant_html(v)


if __name__ == "__main__":
    unittest.main()
