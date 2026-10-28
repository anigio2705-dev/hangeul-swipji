import unittest
from team11_booking_access import booking_access

LEARNER={"id":"learner-1","role":"learner","approved":0}
TEACHER={"id":"teacher-1","role":"teacher","approved":1}
BOOKING={"learner_id":"learner-1","teacher_id":"teacher-1","status":"in_class"}

class BookingBoundaryTests(unittest.TestCase):
    def decision(self,actor,action="join",teacher=None,booking=None):
        return booking_access(LEARNER,teacher or TEACHER,booking or BOOKING,actor,action)

    def test_approved_participants_can_join(self):
        self.assertTrue(self.decision("learner-1")["allowed"])
        self.assertTrue(self.decision("teacher-1")["allowed"])

    def test_outsider_cannot_join_or_view(self):
        for action in ("join","view","complete","settle"):
            self.assertFalse(self.decision("outsider",action)["allowed"])

    def test_revoked_provider_denies_both_participants(self):
        revoked={**TEACHER,"approved":0}
        self.assertEqual(self.decision("learner-1",teacher=revoked)["code"],"FORBIDDEN")

    def test_student_cannot_mark_completed(self):
        self.assertEqual(self.decision("learner-1","complete")["code"],"FORBIDDEN")

    def test_teacher_can_complete_only_active_lesson(self):
        self.assertTrue(self.decision("teacher-1","complete")["allowed"])
        self.assertEqual(self.decision("teacher-1","complete",
            booking={**BOOKING,"status":"reserved"})["code"],"INVALID_STATE")

    def test_reserved_cannot_join(self):
        self.assertEqual(self.decision("learner-1",
            booking={**BOOKING,"status":"reserved"})["code"],"INVALID_STATE")

    def test_cross_booking_identity_rejected(self):
        self.assertEqual(self.decision("teacher-1",
            booking={**BOOKING,"teacher_id":"teacher-2"})["code"],"CONFLICT")

    def test_no_direct_settlement_privilege(self):
        self.assertEqual(self.decision("teacher-1","settle")["code"],"FORBIDDEN")

    def test_unknown_action_fails_closed(self):
        self.assertEqual(self.decision("teacher-1","admin")["code"],"VALIDATION_ERROR")

    def test_missing_booking_field_fails_closed(self):
        self.assertEqual(self.decision("teacher-1",booking={"status":"in_class"})["code"],
                         "VALIDATION_ERROR")

if __name__=="__main__":
    unittest.main()
