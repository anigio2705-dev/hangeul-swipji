"""#118 regression: quality allegations never automatically sanction either party."""
import os
import sqlite3
import tempfile
import unittest

from team14_fair_dispute_review import FairDisputeReview


def case_args(**kw):
    data = dict(case_id="case1", booking_ref="booking1",
                complaint_evidence="evidence1", category="quality")
    data.update(kw)
    return data


def party(role, **kw):
    data = dict(case_id="case1", role=role,
                participant_id="student1" if role == "student" else "teacher1",
                evidence_ref="ev_" + role, statement="My account of the lesson")
    data.update(kw)
    return data


def review(**kw):
    data = dict(case_id="case1", operator_id="operator1",
                verdict="unresolved", rationale="Both statements require review",
                evidence_ref="manual1")
    data.update(kw)
    return data


class FairDisputeTests(unittest.TestCase):
    def setUp(self):
        self.ledger = FairDisputeReview()
        self.ledger.open_case(**case_args())

    def tearDown(self):
        self.ledger.close()

    def test_complaint_alone_cannot_assign_fault_or_take_money(self):
        result = self.ledger.read("case1")
        self.assertEqual("AWAIT_BOTH_PARTIES", result["status"])
        self.assertIsNone(result["operator_review"])
        for key in ("automatic_fault", "automatic_forfeiture", "refund_executed",
                    "payout_blocked", "real_money", "operating_db_connected",
                    "operator_auth_verified"):
            self.assertIs(result[key], False)

    def test_both_parties_required_before_manual_decision(self):
        with self.assertRaisesRegex(ValueError, "both party"):
            self.ledger.record_operator_review(**review())
        self.ledger.add_statement(**party("student"))
        with self.assertRaisesRegex(ValueError, "both party"):
            self.ledger.record_operator_review(**review())
        self.ledger.add_statement(**party("teacher"))
        result = self.ledger.record_operator_review(**review(verdict="teacher_fault"))
        self.assertEqual("MANUAL_REVIEW_RECORDED", result["status"])
        self.assertEqual("teacher_fault", result["operator_review"]["verdict"])
        self.assertFalse(result["automatic_forfeiture"])

    def test_all_categories_and_nonbinding_manual_outcomes(self):
        for i, category in enumerate(("nonperformance", "connectivity", "quality")):
            case_id = "new" + str(i)
            self.ledger.open_case(**case_args(case_id=case_id, category=category))
            self.ledger.add_statement(**party("student", case_id=case_id))
            self.ledger.add_statement(**party("teacher", case_id=case_id))
            result = self.ledger.record_operator_review(
                **review(case_id=case_id, verdict="more_evidence"))
            self.assertEqual(category, result["category"])
            self.assertFalse(result["automatic_fault"])

    def test_same_party_replay_is_idempotent_conflict_rejected(self):
        first = self.ledger.add_statement(**party("student"))
        self.assertEqual(first, self.ledger.add_statement(**party("student")))
        with self.assertRaisesRegex(ValueError, "conflicting"):
            self.ledger.add_statement(**party("student", statement="Changed story"))
        self.assertEqual(1, len(self.ledger.read("case1")["statements"]))

    def test_no_statement_after_manual_decision_and_no_double_decision(self):
        self.ledger.add_statement(**party("student"))
        self.ledger.add_statement(**party("teacher"))
        self.ledger.record_operator_review(**review())
        with self.assertRaisesRegex(ValueError, "already decided"):
            self.ledger.add_statement(**party("student"))
        with self.assertRaisesRegex(ValueError, "already recorded"):
            self.ledger.record_operator_review(**review(verdict="no_fault"))

    def test_independent_operator_and_distinct_participants(self):
        self.ledger.add_statement(**party("student"))
        self.ledger.add_statement(**party("teacher", participant_id="student1"))
        with self.assertRaisesRegex(ValueError, "same participant"):
            self.ledger.record_operator_review(**review())
        self.ledger.open_case(**case_args(case_id="case2"))
        self.ledger.add_statement(**party("student", case_id="case2"))
        self.ledger.add_statement(**party("teacher", case_id="case2"))
        with self.assertRaisesRegex(ValueError, "independent"):
            self.ledger.record_operator_review(
                **review(case_id="case2", operator_id="teacher1"))

    def test_reject_invalid_ids_categories_roles_and_verdicts(self):
        with self.assertRaises(ValueError):
            self.ledger.open_case(**case_args(case_id="../unsafe"))
        with self.assertRaises(ValueError):
            self.ledger.open_case(**case_args(case_id="bad", category="unknown"))
        with self.assertRaises(ValueError):
            self.ledger.add_statement(**party("admin"))
        with self.assertRaises(ValueError):
            self.ledger.add_statement(**party("student", statement=" "))
        with self.assertRaises(ValueError):
            self.ledger.add_statement(**party("student", participant_id="../bad"))
        with self.assertRaises(ValueError):
            self.ledger.record_operator_review(**review(verdict="auto_forfeit"))

    def test_immutable_case_statements_and_decision(self):
        self.ledger.add_statement(**party("student"))
        self.ledger.add_statement(**party("teacher"))
        self.ledger.record_operator_review(**review())
        for sql in (
            "UPDATE fair_case SET category='connectivity' WHERE case_id='case1'",
            "DELETE FROM fair_case WHERE case_id='case1'",
            "UPDATE fair_statement SET statement='x' WHERE case_id='case1'",
            "DELETE FROM fair_statement WHERE case_id='case1'",
            "UPDATE fair_decision SET verdict='teacher_fault' WHERE case_id='case1'",
            "DELETE FROM fair_decision WHERE case_id='case1'",
        ):
            with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError):
                self.ledger.db.execute(sql)

    def test_persistent_isolated_db_and_no_money_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.sqlite")
            first = FairDisputeReview(path)
            try:
                first.open_case(**case_args(case_id="persistent"))
                first.add_statement(**party("student", case_id="persistent"))
            finally:
                first.close()
            second = FairDisputeReview(path)
            try:
                self.assertEqual(1, len(second.read("persistent")["statements"]))
                self.assertIsNone(second.read("persistent")["operator_review"])
                self.assertFalse(second.read("persistent")["real_money"])
            finally:
                second.close()

    def test_missing_case_and_duplicate_case_are_rejected(self):
        with self.assertRaises(KeyError):
            self.ledger.read("missing")
        with self.assertRaises(sqlite3.IntegrityError):
            self.ledger.open_case(**case_args())


if __name__ == "__main__":
    unittest.main()
