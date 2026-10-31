"""B/15 independent QA-only #111; exact product SHA 9b5a90b23f65e69804f8337bf82f8cbb2714ed30."""
import itertools
import unittest

from team14_lesson_disruption_review import review_disruption, case_matrix


def check(**changes):
    args = dict(lesson_kind="single", actor="learner", event_kind="cancel",
                booking_id="qa-111", scheduled_at=1000, observed_at=900,
                evidence_keys=("booking", "notice"))
    args.update(changes)
    return review_disruption(**args)


class BIndependentTask111Tests(unittest.TestCase):
    def assert_never_live(self, r):
        for field in ("refund_authorized", "penalty_authorized", "real_money",
                      "policy_approved", "booking_mutated"):
            self.assertIs(r[field], False)
        self.assertIsNone(r["refund_amount_krw"])
        self.assertIsNone(r["penalty_amount_krw"])

    def test_full_24_scenario_matrix_is_unique_and_review_only(self):
        matrix = case_matrix()
        self.assertEqual(24, len(matrix))
        self.assertEqual(24, len(set((x["lesson_kind"], x["actor"], x["event_kind"])
                                      for x in matrix)))
        for row in matrix:
            self.assertEqual("UNAPPROVED_REVIEW_ONLY", row["refund_policy"])

    def test_all_24_cases_complete_evidence_still_manual_review(self):
        evidence = ("booking", "notice", "attendance", "session", "incident")
        for kind, actor, event in itertools.product(
            ("single", "monthly"), ("learner", "teacher", "system"),
            ("cancel", "no_show", "late", "early_end")
        ):
            args = dict(lesson_kind=kind, actor=actor, event_kind=event,
                        evidence_keys=evidence)
            if kind == "monthly":
                args["monthly_lesson_index"] = 1
            with self.subTest(kind=kind, actor=actor, event=event):
                result = check(**args)
                self.assertEqual("MANUAL_POLICY_REVIEW", result["review_state"])
                self.assert_never_live(result)

    def test_missing_evidence_never_becomes_policy_approval(self):
        for event in ("cancel", "no_show", "late", "early_end"):
            result = check(event_kind=event, evidence_keys=())
            self.assertEqual("MISSING_EVIDENCE", result["review_state"])
            self.assertGreater(len(result["missing_evidence"]), 0)
            self.assert_never_live(result)

    def test_notice_time_boundary_is_strict(self):
        self.assertTrue(check(observed_at=999)["notice_before_scheduled"])
        self.assertFalse(check(observed_at=1000)["notice_before_scheduled"])
        self.assertFalse(check(observed_at=1001)["notice_before_scheduled"])

    def test_untrusted_evidence_rejected(self):
        for bad in ("booking,notice", ["booking", "untrusted"], [1],
                    ["booking"]*21, None):
            with self.subTest(bad=repr(bad)), self.assertRaises(ValueError):
                check(evidence_keys=bad)

    def test_forged_timestamps_and_booking_ids_rejected(self):
        for changes in ({"booking_id": "../secret"}, {"booking_id": ""},
                        {"booking_id": "x"*129}, {"scheduled_at": True},
                        {"observed_at": 1.5}, {"scheduled_at": -1},
                        {"observed_at": 4102444801}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                check(**changes)

    def test_monthly_index_must_be_valid_and_single_must_omit_it(self):
        for bad in (None, 0, 367, True, "1"):
            with self.subTest(bad=repr(bad)), self.assertRaises(ValueError):
                check(lesson_kind="monthly", monthly_lesson_index=bad)
        with self.assertRaises(ValueError):
            check(monthly_lesson_index=1)
        self.assert_never_live(check(lesson_kind="monthly", monthly_lesson_index=366))

    def test_unknown_actor_event_and_lesson_type_rejected(self):
        for changes in ({"lesson_kind": "annual"}, {"actor": "admin"},
                        {"event_kind": "refund_paid"}, {"actor": 1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                check(**changes)


if __name__ == "__main__":
    unittest.main()
