"""#112 isolated incident evidence triage tests; no live API/DB/settlement."""
import unittest

from team14_incident_evidence_review import review_incident, incident_matrix


def evidence(kind, number=1, when=100):
    return {"kind": kind, "reference": "ev_" + kind + "_" + str(number),
            "captured_at": when}


def sample(**changes):
    data = dict(incident_id="incident_1", booking_id="booking_1",
                category="nonperformance", occurred_at=100, as_of=200,
                evidence=[evidence("booking"), evidence("attendance"), evidence("session")],
                learner_statement_received=True, teacher_statement_received=True)
    data.update(changes)
    return review_incident(**data)


class IncidentEvidenceReviewTests(unittest.TestCase):
    def assert_no_side_effects(self, result):
        for key in ("automatic_fault_assigned", "refund_authorized",
                    "penalty_authorized", "payment_enabled", "real_money",
                    "booking_mutated", "policy_approved"):
            self.assertIs(result[key], False, key)
        self.assertEqual("authorized_human_reviewer", result["decision_maker"])

    def test_three_distinct_tracks(self):
        cases = incident_matrix()
        self.assertEqual(3, len(cases))
        self.assertEqual({"nonperformance", "connectivity", "quality"},
                         {c["category"] for c in cases})
        self.assertTrue(all(c["requires_both_party_statements"] for c in cases))

    def test_nonperformance_complete_is_human_review_only(self):
        result = sample()
        self.assertEqual("MANUAL_REVIEW", result["review_state"])
        self.assertEqual([], result["missing_evidence"])
        self.assert_no_side_effects(result)

    def test_connection_needs_connection_log_not_attendance(self):
        result = sample(category="connectivity")
        self.assertEqual("WAIT_EVIDENCE", result["review_state"])
        self.assertEqual(["connection_log"], result["missing_evidence"])
        self.assert_no_side_effects(result)

    def test_quality_requires_feedback(self):
        result = sample(category="quality")
        self.assertEqual(["feedback"], result["missing_evidence"])
        self.assert_no_side_effects(result)

    def test_connection_with_evidence_requires_both_parties(self):
        result = sample(category="connectivity",
                        evidence=[evidence("booking"), evidence("session"),
                                  evidence("connection_log")],
                        teacher_statement_received=False)
        self.assertEqual("WAIT_PARTY_STATEMENTS", result["review_state"])
        self.assertEqual(["teacher"], result["missing_party_statements"])
        self.assert_no_side_effects(result)

    def test_quality_complete_still_never_refunds(self):
        result = sample(category="quality",
                        evidence=[evidence("booking"), evidence("session"),
                                  evidence("feedback")])
        self.assertEqual("MANUAL_REVIEW", result["review_state"])
        self.assert_no_side_effects(result)

    def test_both_missing_statements_order(self):
        result = sample(learner_statement_received=False,
                        teacher_statement_received=False)
        self.assertEqual(["learner", "teacher"], result["missing_party_statements"])

    def test_missing_evidence_takes_precedence_over_statements(self):
        result = sample(evidence=[], learner_statement_received=False)
        self.assertEqual("WAIT_EVIDENCE", result["review_state"])
        self.assertEqual(["attendance", "booking", "session"],
                         result["missing_evidence"])

    def test_extra_verified_evidence_does_not_change_decision(self):
        result = sample(evidence=[evidence("booking"), evidence("attendance"),
                                  evidence("session"), evidence("incident")])
        self.assertEqual(4, result["evidence_reference_count"])
        self.assert_no_side_effects(result)

    def test_invalid_category_and_identifiers(self):
        for change in ({"category": "fraud"}, {"category": []},
                       {"incident_id": "../path"}, {"booking_id": ""},
                       {"booking_id": "a" * 129}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                sample(**change)

    def test_future_and_boolean_times_rejected(self):
        for change in ({"occurred_at": 201}, {"as_of": True},
                       {"occurred_at": -1}, {"as_of": 4102444801}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                sample(**change)

    def test_forged_or_malformed_evidence_rejected(self):
        bad = ([{"kind": "booking", "reference": "b", "captured_at": 100,
                 "verified": True}],
               [{"kind": "unknown", "reference": "b", "captured_at": 100}],
               [{"kind": "booking", "reference": "../b", "captured_at": 100}],
               [{"kind": "booking", "reference": "b", "captured_at": True}],
               [{"kind": "booking", "reference": "b", "captured_at": 201}],
               "booking,session",
               [evidence("booking")] * 21)
        for items in bad:
            with self.subTest(items=str(items)[:60]), self.assertRaises(ValueError):
                sample(evidence=items)

    def test_duplicate_reference_rejected(self):
        with self.assertRaises(ValueError):
            sample(evidence=[evidence("booking"), evidence("booking")])

    def test_statement_flags_must_be_boolean(self):
        for change in ({"learner_statement_received": 1},
                       {"teacher_statement_received": "yes"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                sample(**change)

    def test_no_raw_statement_or_sensitive_evidence_echo(self):
        result = sample()
        self.assertNotIn("statement_text", result)
        self.assertNotIn("evidence", result)
        self.assertEqual("booking_1", result["booking_id"])


if __name__ == "__main__":
    unittest.main()
