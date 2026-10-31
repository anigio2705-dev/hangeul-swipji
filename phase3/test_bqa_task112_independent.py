"""B/15 independent QA-only #112 exact product SHA 444bc69a...; no live DB."""
import itertools
import unittest

from team14_incident_evidence_review import review_incident, incident_matrix

REQUIRED = {
    "nonperformance": ("booking", "attendance", "session"),
    "connectivity": ("booking", "connection_log", "session"),
    "quality": ("booking", "session", "feedback"),
}
DENY = ("automatic_fault_assigned", "refund_authorized", "penalty_authorized",
        "payment_enabled", "real_money", "booking_mutated", "policy_approved")


def ev(kind, n=0, at=100):
    return {"kind": kind, "reference": f"ref_{kind}_{n}", "captured_at": at}


def triage(category="nonperformance", **kw):
    data = dict(incident_id="inc_1", booking_id="book_1", category=category,
                occurred_at=100, as_of=200,
                evidence=[ev(k) for k in REQUIRED[category]],
                learner_statement_received=True, teacher_statement_received=True)
    data.update(kw)
    return review_incident(**data)


class BIndependentTask112Tests(unittest.TestCase):
    def no_effects(self, output):
        for field in DENY:
            self.assertIs(output[field], False, field)
        self.assertEqual("authorized_human_reviewer", output["decision_maker"])
        self.assertNotIn("evidence", output)
        self.assertNotIn("statement_text", output)

    def test_all_category_evidence_permutations_stay_manual(self):
        for category, kinds in REQUIRED.items():
            for permutation in itertools.permutations(kinds):
                with self.subTest(category=category, permutation=permutation):
                    out = triage(category, evidence=[ev(k) for k in permutation])
                    self.assertEqual("MANUAL_REVIEW", out["review_state"])
                    self.assertEqual([], out["missing_evidence"])
                    self.no_effects(out)

    def test_category_specific_missing_evidence_is_never_waived(self):
        for category, kinds in REQUIRED.items():
            for absent in kinds:
                with self.subTest(category=category, absent=absent):
                    out = triage(category, evidence=[ev(k) for k in kinds if k != absent])
                    self.assertEqual("WAIT_EVIDENCE", out["review_state"])
                    self.assertEqual([absent], out["missing_evidence"])
                    self.no_effects(out)

    def test_statements_are_required_for_every_category(self):
        for category in REQUIRED:
            for learner, teacher in itertools.product((False, True), repeat=2):
                out = triage(category, learner_statement_received=learner,
                             teacher_statement_received=teacher)
                self.assertEqual("MANUAL_REVIEW" if learner and teacher
                                 else "WAIT_PARTY_STATEMENTS", out["review_state"])
                self.assertEqual([p for p, received in (("learner", learner),
                                  ("teacher", teacher)) if not received],
                                 out["missing_party_statements"])
                self.no_effects(out)

    def test_missing_evidence_has_priority_over_statements(self):
        for category in REQUIRED:
            out = triage(category, evidence=[], learner_statement_received=False,
                         teacher_statement_received=False)
            self.assertEqual("WAIT_EVIDENCE", out["review_state"])
            self.assertEqual(sorted(REQUIRED[category]), out["missing_evidence"])
            self.no_effects(out)

    def test_same_reference_different_kind_rejected(self):
        items = [ev("booking"), ev("attendance"), ev("session")]
        items[1]["reference"] = items[0]["reference"]
        with self.assertRaises(ValueError):
            triage(evidence=items)

    def test_untrusted_metadata_or_unbounded_evidence_rejected(self):
        for bad in ([dict(ev("booking"), verified=True)],
                    [dict(ev("booking"), raw_statement="secret")],
                    [dict(ev("booking"), captured_at=True)],
                    [dict(ev("booking"), reference="../secret")],
                    [ev("booking", i) for i in range(21)],
                    {"kind": "booking"}, "booking,session"):
            with self.subTest(case=str(bad)[:40]), self.assertRaises(ValueError):
                triage(evidence=bad)

    def test_future_and_invalid_time_or_flag_never_authorize(self):
        for change in ({"as_of": 99}, {"occurred_at": 201},
                       {"evidence": [ev("booking", at=201)]},
                       {"learner_statement_received": 1},
                       {"teacher_statement_received": "true"},
                       {"occurred_at": 4102444801},
                       {"booking_id": "x" * 129}):
            with self.subTest(change=str(change)[:50]), self.assertRaises(ValueError):
                triage(**change)

    def test_twenty_evidence_limit_and_no_raw_data_echo(self):
        base = [ev(k) for k in REQUIRED["nonperformance"]]
        extra = [ev("incident", i) for i in range(17)]
        out = triage(evidence=base + extra)
        self.assertEqual(20, out["evidence_reference_count"])
        self.assertEqual("MANUAL_REVIEW", out["review_state"])
        self.no_effects(out)

    def test_matrix_is_nonbinding_and_deterministic(self):
        matrix = incident_matrix()
        self.assertEqual(3, len(matrix))
        for row in matrix:
            self.assertEqual("HUMAN_REVIEW_ONLY", row["resolution"])
            self.assertTrue(row["requires_both_party_statements"])
            self.assertEqual(sorted(REQUIRED[row["category"]]), row["required_evidence"])
        self.assertEqual(matrix, incident_matrix())


if __name__ == "__main__":
    unittest.main()
