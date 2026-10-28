"""Team11 boundary tests: authorization and simulated settlement handoff."""
import unittest
from team11_shared_boundary import (
    authorize_provider, authorize_student, lesson_completion_event,
    validate_completion_event, settlement_reference, http_error_contract,
    match_state_contract,
)

def sample_event():
    return lesson_completion_event(event_id="event-1", booking_id="booking-1",
        learner_id="student-1", provider_id="teacher-1",
        kind="professional_teacher", amount_krw=15000)


class Team11BoundaryTests(unittest.TestCase):
    def test_legacy_learner_and_approved_teacher(self):
        self.assertTrue(authorize_student({"role":"learner","approved":0}).allowed)
        self.assertFalse(authorize_provider({"role":"learner","approved":1},
                         "professional_teacher").allowed)
        self.assertTrue(authorize_provider({"role":"teacher","approved":1},
                        "professional_teacher").allowed)

    def test_legacy_teacher_conversation_compatibility(self):
        self.assertTrue(authorize_provider({"role":"teacher","approved":1},
            "conversation_partner").allowed)
        self.assertFalse(authorize_provider({"role":"teacher","approved":0},
            "conversation_partner").allowed)

    def test_legacy_unapproved_provider_denied(self):
        for role, kind in (("teacher","professional_teacher"),
                           ("partner","conversation_partner")):
            decision = authorize_provider({"role":role,"approved":0},kind)
            self.assertEqual(decision.error_code,"FORBIDDEN")

    def test_candidate_multirole_no_implicit_grant(self):
        decision = authorize_provider(["learner","teacher"],
            "professional_teacher",candidate=True,
            approvals={"professional_teacher":"requested"})
        self.assertFalse(decision.allowed)
        self.assertTrue(authorize_student(["learner","teacher"],candidate=True).allowed)

    def test_candidate_explicit_approval(self):
        self.assertTrue(authorize_provider(["learner","teacher"],
            "professional_teacher",candidate=True,
            approvals={"professional_teacher":"approved"}).allowed)

    def test_invalid_kind_rejected(self):
        self.assertEqual(authorize_provider({"role":"teacher","approved":1},
            "admin").error_code,"VALIDATION_ERROR")

    def test_completion_round_trip(self):
        event=sample_event()
        self.assertEqual(validate_completion_event(event),event)
        self.assertEqual(event["currency"],"KRW")

    def test_completion_rejects_unapproved_state_and_self_booking(self):
        with self.assertRaises(ValueError):
            lesson_completion_event(event_id="e",booking_id="b",learner_id="u",
                provider_id="u",kind="professional_teacher",amount_krw=1)
        with self.assertRaises(ValueError):
            lesson_completion_event(event_id="e",booking_id="b",learner_id="u",
                provider_id="t",kind="professional_teacher",amount_krw=1,
                state="in_class")

    def test_completion_rejects_negative_and_bool_amount(self):
        for amount in (-1,True):
            with self.subTest(amount=amount),self.assertRaises(ValueError):
                lesson_completion_event(event_id="e",booking_id="b",
                    learner_id="u",provider_id="t",
                    kind="professional_teacher",amount_krw=amount)

    def test_tampered_event_rejected(self):
        for key,value in (("currency","USD"),("event_type","lesson.refunded"),
                          ("amount",True)):
            event=sample_event()
            event[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                validate_completion_event(event)

    def test_monthly_simulator_reference(self):
        ref=settlement_reference(sample_event(),month_id="2026-10",lesson_index=0)
        self.assertEqual(ref["booking_id"],"booking-1")
        self.assertEqual(ref["currency"],"KRW")
        with self.assertRaises(ValueError):
            settlement_reference(sample_event(),month_id="2026-10",lesson_index=True)

    def test_errors_and_match_states(self):
        self.assertEqual(http_error_contract(403)["code"],"FORBIDDEN")
        self.assertFalse(match_state_contract("waiting")["persisted"])
        self.assertTrue(match_state_contract("active")["persisted"])


if __name__=="__main__":
    unittest.main()
