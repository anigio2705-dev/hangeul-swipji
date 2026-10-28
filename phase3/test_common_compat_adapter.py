"""Independent adapter integration-contract tests, no server or database writes."""
import unittest
from common_compat_adapter import (
    from_legacy_user, from_candidate, matching_side, normalize_match_state,
    normalize_error, month_lesson_reference,
)


class CompatibilityAdapterTests(unittest.TestCase):
    def test_legacy_learner_cannot_provide(self):
        view = from_legacy_user({"role":"learner","approved":1})
        self.assertTrue(matching_side(view, "learner"))
        self.assertFalse(matching_side(view, "provider"))

    def test_legacy_unapproved_provider_blocked(self):
        for role in ("partner", "teacher"):
            with self.subTest(role=role):
                view = from_legacy_user({"role":role,"approved":0})
                self.assertFalse(matching_side(view, "provider"))
                self.assertFalse(matching_side(view, "learner"))

    def test_legacy_approved_provider_compatible(self):
        for role in ("partner", "teacher"):
            view = from_legacy_user({"role":role,"approved":1})
            self.assertTrue(matching_side(view, "provider"))
            self.assertFalse(matching_side(view, "learner"))

    def test_candidate_multirole_requires_approval(self):
        view = from_candidate(["learner","teacher"], {"professional_teacher":"requested"})
        self.assertTrue(matching_side(view,"learner"))
        self.assertFalse(matching_side(view,"provider"))

    def test_candidate_multirole_approved_provider(self):
        view = from_candidate(["learner","teacher"], {"professional_teacher":"approved"})
        self.assertTrue(matching_side(view,"learner"))
        self.assertTrue(matching_side(view,"provider"))

    def test_invalid_flags_and_role_injection(self):
        for approved in (None, 2, "1", -1):
            with self.assertRaises(ValueError):
                from_legacy_user({"role":"teacher","approved":approved})
        with self.assertRaises(ValueError):
            from_candidate(["learner","owner"], {})

    def test_candidate_unapproved_partner_cannot_escalate(self):
        for state in ("requested","rejected","suspended"):
            view = from_candidate(["learner","partner"], {"conversation_partner":state})
            self.assertFalse(matching_side(view,"provider"))

    def test_api_vs_persisted_match_state(self):
        self.assertFalse(normalize_match_state("waiting")["persisted"])
        self.assertTrue(normalize_match_state("active")["persisted"])
        with self.assertRaises(ValueError):
            normalize_match_state("paid")

    def test_http_error_mapping(self):
        self.assertEqual(normalize_error(403), "FORBIDDEN")
        self.assertEqual(normalize_error(409), "CONFLICT")
        with self.assertRaises(ValueError):
            normalize_error(500)

    def test_month_currency_and_scoped_lesson(self):
        self.assertEqual(month_lesson_reference("month-1",0,"KRW")["lesson_index"],0)
        with self.assertRaises(ValueError):
            month_lesson_reference("month-1",0,"USD")
        with self.assertRaises(ValueError):
            month_lesson_reference("month-1",True,"KRW")


if __name__ == "__main__":
    unittest.main()
