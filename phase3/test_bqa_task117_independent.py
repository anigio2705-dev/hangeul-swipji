"""B/15 QA-only adversarial tests for product #117 SHA be6d7f1a92f6951e8f53199fbd5d6b0cbfbd1d3b.
Independent tests only; no product edits, no live database, sanctions, or money.
"""
import copy
import sqlite3
import unittest
from pathlib import Path

from team14_fair_dispute_review import FairDisputeReview
from team14_teacher_accountability_review import (
    review_teacher_accountability, TeacherAppealReview,
)


def legitimate_case():
    db = FairDisputeReview()
    try:
        db.open_case(case_id="bqa117", booking_ref="booking117",
                     complaint_evidence="complaint117", category="quality")
        db.add_statement(case_id="bqa117", role="student", participant_id="student117",
                         evidence_ref="studentEvidence", statement="Lesson did not happen")
        db.add_statement(case_id="bqa117", role="teacher", participant_id="teacher117",
                         evidence_ref="teacherEvidence", statement="Connection problem")
        db.record_operator_review(case_id="bqa117", operator_id="operator117",
                                  verdict="teacher_fault", rationale="Both sides reviewed",
                                  evidence_ref="operatorEvidence")
        return db.read("bqa117")
    finally:
        db.close()


class IndependentTeacherAccountabilityQA(unittest.TestCase):
    def test_01_real_fixture_nonbinding_even_for_repeat_fault(self):
        result = review_teacher_accountability(
            legitimate_case(), prior_confirmed_cases=4, financial_risk_verified=True)
        self.assertTrue(all(x["candidate"] for x in result["criteria"]))
        self.assertTrue(all(not x["authorized"] and not x["executed"] for x in result["criteria"]))
        for key in ("warning_sent", "exposure_changed", "settlement_blocked",
                    "account_restricted", "real_money", "policy_approved"):
            self.assertFalse(result[key])

    def test_02_blank_operator_cannot_confirm_teacher_fault(self):
        """An empty operator identity must never count as independent adjudication."""
        forged = legitimate_case()
        forged["operator_review"]["operator_id"] = ""
        with self.assertRaises(ValueError):
            review_teacher_accountability(forged)

    def test_03_path_like_operator_cannot_confirm_teacher_fault(self):
        """The source #118 enforces _id; #117 must not weaken its identity contract."""
        forged = legitimate_case()
        forged["operator_review"]["operator_id"] = "../forged"
        with self.assertRaises(ValueError):
            review_teacher_accountability(forged)

    def test_04_invalid_operator_evidence_cannot_confirm_fault(self):
        forged = legitimate_case()
        forged["operator_review"]["evidence_ref"] = "../forged"
        with self.assertRaises(ValueError):
            review_teacher_accountability(forged)

    def test_05_party_as_operator_is_rejected(self):
        forged = legitimate_case()
        forged["operator_review"]["operator_id"] = "student117"
        with self.assertRaises(ValueError):
            review_teacher_accountability(forged)

    def test_06_false_allegation_without_verdict_cannot_become_candidate(self):
        case = legitimate_case()
        case["operator_review"] = None
        result = review_teacher_accountability(case, prior_confirmed_cases=10,
                                                financial_risk_verified=True)
        self.assertFalse(result["appeal_available_for_review"])
        self.assertTrue(all(not c["candidate"] for c in result["criteria"]))

    def test_07_appeal_reviewer_independence_and_immutability(self):
        appeal = TeacherAppealReview()
        try:
            appeal.file_appeal(dispute=legitimate_case(), teacher_id="teacher117",
                              reason="Please reconsider", evidence_ref="appeal117")
            for actor in ("student117", "teacher117", "operator117"):
                with self.assertRaises(ValueError):
                    appeal.decide_appeal(case_id="bqa117", reviewer_id=actor,
                                        outcome="reopen_investigation",
                                        rationale="Not independent", evidence_ref="review117")
            row = appeal.decide_appeal(case_id="bqa117", reviewer_id="reviewer117",
                                      outcome="reopen_investigation",
                                      rationale="Reconsider evidence", evidence_ref="review117")
            self.assertEqual("NONBINDING_REVIEW_RECORDED", row["status"])
            self.assertFalse(row["sanction_executed"])
            with self.assertRaises(sqlite3.IntegrityError):
                appeal.db.execute("UPDATE teacher_appeal_resolution SET outcome='uphold_review'")
        finally:
            appeal.close()

    def test_08_duplicate_appeal_cannot_overwrite(self):
        appeal = TeacherAppealReview()
        try:
            args = dict(dispute=legitimate_case(), teacher_id="teacher117",
                        reason="Review", evidence_ref="appeal117")
            appeal.file_appeal(**args)
            with self.assertRaises(sqlite3.IntegrityError):
                appeal.file_appeal(**args)
        finally:
            appeal.close()

    def test_09_review_ui_has_no_enabled_actions_or_scripts(self):
        page = (Path(__file__).resolve().parent / "teacher-accountability-review.html").read_text(encoding="utf-8")
        self.assertIn("default-src 'none'", page)
        self.assertNotIn("<script", page.lower())
        self.assertEqual(page.lower().count("<button"), page.lower().count("<button disabled"))
        self.assertGreaterEqual(page.lower().count("<button disabled"), 3)


if __name__ == "__main__":
    unittest.main()
