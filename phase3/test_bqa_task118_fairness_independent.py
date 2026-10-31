"""B/15 independent exact-SHA #118: no allegation-only guilt, no unauthenticated money."""
import os
import sqlite3
import tempfile
import unittest
from team14_fair_dispute_review import FairDisputeReview

class BQA118Fairness(unittest.TestCase):
    def setUp(self):
        self.audit = FairDisputeReview()
        self.audit.open_case(case_id="c1", booking_ref="booking_1",
                             complaint_evidence="ev_1", category="quality")
    def tearDown(self):
        self.audit.close()
    def statement(self, role, case_id="c1", participant_id=None, evidence_ref=None):
        return self.audit.add_statement(
            case_id=case_id, role=role,
            participant_id=participant_id or ("student_1" if role=="student" else "teacher_1"),
            evidence_ref=evidence_ref or ("proof_"+role),
            statement="Independent account from "+role)
    def decision(self, case_id="c1", operator_id="operator_1", verdict="teacher_fault"):
        return self.audit.record_operator_review(
            case_id=case_id, operator_id=operator_id, verdict=verdict,
            rationale="Manual review with two statements", evidence_ref="review_evidence")
    def test_single_allegation_cannot_set_fault_or_money(self):
        state=self.audit.read("c1")
        self.assertIsNone(state["operator_review"])
        self.assertEqual("AWAIT_BOTH_PARTIES",state["status"])
        for key in ("automatic_fault","automatic_forfeiture","refund_executed",
                    "payout_blocked","real_money","operating_db_connected"):
            self.assertIs(state[key],False)
        with self.assertRaisesRegex(ValueError,"both party"):
            self.decision()
    def test_one_party_cannot_decide_even_if_operator_named(self):
        self.statement("student")
        with self.assertRaisesRegex(ValueError,"both party"):
            self.decision()
        self.assertIsNone(self.audit.read("c1")["operator_review"])
    def test_two_party_review_never_authorizes_sanction(self):
        self.statement("student");self.statement("teacher")
        state=self.decision()
        self.assertEqual("MANUAL_REVIEW_RECORDED",state["status"])
        self.assertEqual("teacher_fault",state["operator_review"]["verdict"])
        for key in ("automatic_fault","automatic_forfeiture","refund_executed",
                    "payout_blocked","real_money","operator_auth_verified"):
            self.assertIs(state[key],False)
    def test_operator_cannot_be_either_party(self):
        self.statement("student");self.statement("teacher")
        for actor in ("student_1","teacher_1"):
            with self.subTest(actor=actor),self.assertRaisesRegex(ValueError,"independent"):
                self.decision(operator_id=actor)
        self.assertIsNone(self.audit.read("c1")["operator_review"])
    def test_replay_identical_statement_no_duplicate_and_conflict_rejected(self):
        self.statement("student")
        self.statement("student")
        self.assertEqual(1,self.audit.db.execute(
            "SELECT COUNT(*) FROM fair_statement WHERE case_id='c1'").fetchone()[0])
        with self.assertRaisesRegex(ValueError,"conflicting"):
            self.statement("student",evidence_ref="changed_proof")
        self.assertEqual(1,len(self.audit.read("c1")["statements"]))
    def test_decision_immutable_and_no_late_statement(self):
        self.statement("student");self.statement("teacher");self.decision()
        with self.assertRaisesRegex(ValueError,"already decided"):
            self.statement("student")
        with self.assertRaisesRegex(ValueError,"already recorded"):
            self.decision(verdict="no_fault")
        for sql in ("UPDATE fair_decision SET verdict='no_fault' WHERE case_id='c1'",
                    "DELETE FROM fair_decision WHERE case_id='c1'",
                    "DELETE FROM fair_statement WHERE case_id='c1'"):
            with self.subTest(sql=sql),self.assertRaises(sqlite3.IntegrityError):
                self.audit.db.execute(sql)
    def test_cross_case_evidence_does_not_count_as_other_party(self):
        self.audit.open_case(case_id="c2",booking_ref="booking_2",
                             complaint_evidence="ev_2",category="connectivity")
        self.statement("student","c1");self.statement("teacher","c2")
        with self.assertRaisesRegex(ValueError,"both party"):
            self.decision("c1")
        with self.assertRaisesRegex(ValueError,"both party"):
            self.decision("c2")
    def test_distinct_roles_cannot_be_same_identity(self):
        self.statement("student")
        self.statement("teacher",participant_id="student_1")
        with self.assertRaisesRegex(ValueError,"same participant"):
            self.decision()
    def test_sql_like_identifiers_rejected_before_writes(self):
        for bad in ("../x","a';DROP TABLE fair_case;--","a/b","", "a"*129):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                self.audit.open_case(case_id=bad,booking_ref="b",
                                     complaint_evidence="ev",category="quality")
        self.assertEqual(1,self.audit.db.execute("SELECT COUNT(*) FROM fair_case").fetchone()[0])
    def test_restart_preserves_only_explicit_records(self):
        with tempfile.TemporaryDirectory() as td:
            path=os.path.join(td,"qa.sqlite")
            one=FairDisputeReview(path)
            try:
                one.open_case(case_id="persist",booking_ref="b",
                              complaint_evidence="ev",category="quality")
                one.add_statement(case_id="persist",role="student",participant_id="s",
                                  evidence_ref="evs",statement="statement")
            finally:
                one.close()
            two=FairDisputeReview(path)
            try:
                state=two.read("persist")
                self.assertEqual(1,len(state["statements"]))
                self.assertIsNone(state["operator_review"])
                self.assertIs(state["real_money"],False)
            finally:
                two.close()

if __name__=="__main__":
    unittest.main()
