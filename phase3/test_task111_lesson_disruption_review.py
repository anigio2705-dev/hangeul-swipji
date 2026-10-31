"""#111 isolated review matrix regressions; no live booking/refund writes."""
import unittest
from team14_lesson_disruption_review import review_disruption, case_matrix


def sample(**updates):
    args = dict(lesson_kind="single", actor="learner", event_kind="cancel",
                booking_id="b-1", scheduled_at=1000, observed_at=900,
                evidence_keys=["booking", "notice"])
    args.update(updates)
    return review_disruption(**args)


class LessonDisruptionTests(unittest.TestCase):
    def test_all_24_cases_are_explicit_and_not_refund_policy(self):
        cases = case_matrix()
        self.assertEqual(24, len(cases))
        self.assertEqual(24, len({(c["lesson_kind"], c["actor"], c["event_kind"]) for c in cases}))
        self.assertTrue(all(c["refund_policy"] == "UNAPPROVED_REVIEW_ONLY" for c in cases))

    def test_complete_evidence_never_approves_money(self):
        r = sample()
        self.assertEqual("MANUAL_POLICY_REVIEW", r["review_state"])
        for k in ("refund_authorized", "penalty_authorized", "real_money", "policy_approved", "booking_mutated"):
            self.assertIs(r[k], False)
        self.assertIsNone(r["refund_amount_krw"])

    def test_missing_evidence_stays_blocked(self):
        r = sample(evidence_keys=["booking"])
        self.assertEqual("MISSING_EVIDENCE", r["review_state"])
        self.assertEqual(["notice"], r["missing_evidence"])

    def test_monthly_requires_index_and_does_not_set_refund(self):
        r = sample(lesson_kind="monthly", monthly_lesson_index=4)
        self.assertEqual(4, r["monthly_lesson_index"])
        self.assertIsNone(r["refund_amount_krw"])

    def test_no_show_requires_attendance(self):
        r = sample(event_kind="no_show", evidence_keys=["booking"])
        self.assertIn("attendance", r["missing_evidence"])

    def test_late_requires_session_evidence(self):
        r = sample(event_kind="late", evidence_keys=["booking", "attendance"])
        self.assertIn("session", r["missing_evidence"])

    def test_early_end_requires_session_evidence(self):
        r = sample(event_kind="early_end", evidence_keys=["booking", "attendance", "session"])
        self.assertEqual("MANUAL_POLICY_REVIEW", r["review_state"])

    def test_notice_timing_boundary(self):
        self.assertTrue(sample(observed_at=999)["notice_before_scheduled"])
        self.assertFalse(sample(observed_at=1000)["notice_before_scheduled"])

    def test_actor_is_explanatory_not_automatic_blame(self):
        for actor in ("learner", "teacher", "system"):
            r = sample(actor=actor)
            self.assertFalse(r["penalty_authorized"])

    def test_invalid_enum_rejected(self):
        for update in ({"lesson_kind": "annual"}, {"actor": "admin"},
                       {"event_kind": "paid"}, {"actor": []}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                sample(**update)

    def test_invalid_identifiers_and_timestamps(self):
        for update in ({"booking_id": "../b"}, {"booking_id": ""},
                       {"scheduled_at": True}, {"observed_at": -1}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                sample(**update)

    def test_untrusted_evidence_rejected(self):
        for evidence in ("booking,notice", ["fake"], [1], ["booking"] * 21):
            with self.subTest(evidence=evidence), self.assertRaises(ValueError):
                sample(evidence_keys=evidence)

    def test_monthly_index_validation(self):
        for index in (None, 0, True, 367):
            with self.subTest(index=index), self.assertRaises(ValueError):
                sample(lesson_kind="monthly", monthly_lesson_index=index)
        with self.assertRaises(ValueError):
            sample(monthly_lesson_index=1)


if __name__ == "__main__":
    unittest.main()
