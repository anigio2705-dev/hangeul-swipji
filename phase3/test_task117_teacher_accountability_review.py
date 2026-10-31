"""#117 regression: teacher sanctions require confirmed independent findings and appeal."""
import os
import sqlite3
import tempfile
import unittest
from team14_teacher_accountability_review import (
    review_teacher_accountability, TeacherAppealReview)
from team14_fair_dispute_review import FairDisputeReview


def dispute(verdict="teacher_fault"):
    db = FairDisputeReview()
    try:
        db.open_case(case_id="case117", booking_ref="book117",
                     complaint_evidence="ev1", category="quality")
        db.add_statement(case_id="case117", role="student", participant_id="student1",
                         evidence_ref="studentEv", statement="Class did not start")
        db.add_statement(case_id="case117", role="teacher", participant_id="teacher1",
                         evidence_ref="teacherEv", statement="Connection failed")
        if verdict is not None:
            db.record_operator_review(case_id="case117", operator_id="operator1",
                                      verdict=verdict, rationale="Reviewed both accounts",
                                      evidence_ref="operatorEv")
        return db.read("case117")
    finally:
        db.close()


class TeacherAccountabilityTests(unittest.TestCase):
    def test_allegation_only_never_sanctions(self):
        r = review_teacher_accountability(dispute(None))
        self.assertFalse(r["appeal_available_for_review"])
        self.assertTrue(all(not x["candidate"] for x in r["criteria"]))
        self.assertTrue(all(not x["authorized"] for x in r["criteria"]))

    def test_other_verdict_never_sanctions(self):
        for verdict in ("no_fault", "student_fault", "more_evidence", "unresolved"):
            with self.subTest(verdict=verdict):
                self.assertFalse(any(x["candidate"] for x in
                                     review_teacher_accountability(dispute(verdict))["criteria"]))

    def test_confirmed_fault_has_review_only_warning(self):
        r = review_teacher_accountability(dispute())
        self.assertEqual([True, False, False, False],
                         [x["candidate"] for x in r["criteria"]])
        self.assertEqual("MANUAL_TEACHER_FAULT_RECORDED", r["finding"])
        self.assertTrue(r["appeal_available_for_review"])

    def test_repeat_and_risk_criteria_do_not_authorize_actions(self):
        r = review_teacher_accountability(dispute(), prior_confirmed_cases=3,
                                          financial_risk_verified=True)
        self.assertTrue(all(x["candidate"] for x in r["criteria"]))
        self.assertTrue(all(not x["authorized"] and not x["executed"]
                            for x in r["criteria"]))
        for flag in ("policy_approved", "identity_verified", "live_booking_verified",
                     "automatic_sanction", "warning_sent", "exposure_changed",
                     "settlement_blocked", "account_restricted", "real_money"):
            self.assertIs(r[flag], False)

    def test_invalid_counts_and_flags_fail_closed(self):
        for value in (-1, True, 1.2, "3", 1001):
            with self.assertRaises(ValueError):
                review_teacher_accountability(dispute(), prior_confirmed_cases=value)
        for value in (1, "yes", None):
            with self.assertRaises(ValueError):
                review_teacher_accountability(dispute(), financial_risk_verified=value)

    def test_forged_manual_finding_rejected(self):
        r = dispute()
        r["operator_review"]["operator_id"] = "teacher1"
        with self.assertRaises(ValueError):
            review_teacher_accountability(r)
        r = dispute()
        r["statements"][1]["participant_id"] = "student1"
        with self.assertRaises(ValueError):
            review_teacher_accountability(r)

    def test_invalid_manual_operator_identity_never_confirms_fault(self):
        for operator_id in ("", "../forged", "bad/id", " ", "x" * 129, None, True):
            with self.subTest(operator_id=operator_id):
                snapshot = dispute()
                snapshot["operator_review"]["operator_id"] = operator_id
                with self.assertRaises(ValueError):
                    review_teacher_accountability(snapshot)

    def test_invalid_manual_evidence_never_confirms_fault(self):
        for evidence_ref in ("", "../forged", "bad/id", " ", "x" * 129, None, 7):
            with self.subTest(evidence_ref=evidence_ref):
                snapshot = dispute()
                snapshot["operator_review"]["evidence_ref"] = evidence_ref
                with self.assertRaises(ValueError):
                    review_teacher_accountability(snapshot)

    def test_invalid_manual_rationale_never_confirms_fault(self):
        for rationale in ("", "  ", None, True, "x" * 2001):
            with self.subTest(rationale=str(rationale)[:30]):
                snapshot = dispute()
                snapshot["operator_review"]["rationale"] = rationale
                with self.assertRaises(ValueError):
                    review_teacher_accountability(snapshot)

    def test_appeal_requires_confirmed_fault(self):
        with TeacherAppealReviewFixture() as a:
            with self.assertRaises(ValueError):
                a.file_appeal(dispute=dispute(None), teacher_id="teacher1",
                              reason="Please reconsider", evidence_ref="newEv")

    def test_only_named_teacher_can_submit_fixture(self):
        with TeacherAppealReviewFixture() as a:
            with self.assertRaises(ValueError):
                a.file_appeal(dispute=dispute(), teacher_id="stranger",
                              reason="Please reconsider", evidence_ref="newEv")

    def test_appeal_and_independent_review_are_append_only(self):
        with TeacherAppealReviewFixture() as a:
            a.file_appeal(dispute=dispute(), teacher_id="teacher1",
                          reason="Evidence was overlooked", evidence_ref="newEv")
            for reviewer in ("student1", "teacher1", "operator1"):
                with self.assertRaises(ValueError):
                    a.decide_appeal(case_id="case117", reviewer_id=reviewer,
                                    outcome="reopen_investigation",
                                    rationale="Needs review", evidence_ref="ev2")
            result = a.decide_appeal(case_id="case117", reviewer_id="reviewer2",
                                     outcome="reopen_investigation",
                                     rationale="Independent recheck", evidence_ref="ev2")
            self.assertEqual("NONBINDING_REVIEW_RECORDED", result["status"])
            self.assertFalse(result["sanction_executed"])
            with self.assertRaises(sqlite3.IntegrityError):
                a.decide_appeal(case_id="case117", reviewer_id="reviewer3",
                                outcome="uphold_review", rationale="Duplicate",
                                evidence_ref="ev3")
            for sql in ("UPDATE teacher_appeal SET reason='x'",
                        "DELETE FROM teacher_appeal",
                        "UPDATE teacher_appeal_resolution SET outcome='uphold_review'",
                        "DELETE FROM teacher_appeal_resolution"):
                with self.assertRaises(sqlite3.IntegrityError):
                    a.db.execute(sql)

    def test_duplicate_appeal_rejected(self):
        with TeacherAppealReviewFixture() as a:
            params = dict(dispute=dispute(), teacher_id="teacher1",
                          reason="Please reconsider", evidence_ref="newEv")
            a.file_appeal(**params)
            with self.assertRaises(sqlite3.IntegrityError):
                a.file_appeal(**params)

    def test_invalid_outcome_and_injection_rejected(self):
        with TeacherAppealReviewFixture() as a:
            a.file_appeal(dispute=dispute(), teacher_id="teacher1",
                          reason="Please reconsider", evidence_ref="newEv")
            with self.assertRaises(ValueError):
                a.decide_appeal(case_id="case117", reviewer_id="reviewer2",
                                outcome="auto_suspend", rationale="No",
                                evidence_ref="ev2")
            with self.assertRaises(ValueError):
                a.decide_appeal(case_id="../case117", reviewer_id="reviewer2",
                                outcome="uphold_review", rationale="No",
                                evidence_ref="ev2")

    def test_sqlite_reopen_preserves_nonbinding_appeal(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "review.sqlite")
            a = TeacherAppealReview(path)
            a.file_appeal(dispute=dispute(), teacher_id="teacher1",
                          reason="Please reconsider", evidence_ref="newEv")
            a.close()
            b = TeacherAppealReview(path)
            try:
                self.assertEqual("AWAIT_INDEPENDENT_REVIEW", b.read("case117")["status"])
                self.assertFalse(b.read("case117")["real_money"])
            finally:
                b.close()


class TeacherAppealReviewFixture:
    def __enter__(self):
        self.review = TeacherAppealReview()
        return self.review
    def __exit__(self, *args):
        self.review.close()


if __name__ == "__main__":
    unittest.main()
