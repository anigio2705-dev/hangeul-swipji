"""#119 isolated learner remedy options: never enable an unapproved action."""
import pathlib
import unittest

from team14_learner_remedy_preview import remedy_preview


def preview(**kw):
    p = dict(case_ref="case_1", remaining_lessons=3,
             dispute_state="review_pending", policy_fixture=None)
    p.update(kw)
    return remedy_preview(**p)


class Task119RemedyPreviewTests(unittest.TestCase):
    def test_all_three_options_visible_but_blocked_without_policy(self):
        r = preview()
        self.assertEqual(["makeup_lesson", "change_tutor",
                          "unused_lessons_refund"], [x["id"] for x in r["options"]])
        self.assertTrue(all(x["shown"] for x in r["options"]))
        self.assertTrue(all(x["status"] == "POLICY_NOT_APPROVED"
                            for x in r["options"]))
        self.assertTrue(all(not x["student_can_select"] for x in r["options"]))

    def test_test_fixture_only_simulates_no_real_selection(self):
        r = preview(policy_fixture={"version": "fixture_1",
                                    "enabled_options": ["makeup_lesson",
                                                        "unused_lessons_refund"]})
        self.assertEqual(["SIMULATION_ONLY", "POLICY_NOT_APPROVED",
                          "SIMULATION_ONLY"], [x["status"] for x in r["options"]])
        self.assertFalse(r["policy_approved"])
        self.assertTrue(all(not x["student_can_select"] for x in r["options"]))

    def test_no_remaining_lessons_no_action(self):
        r = preview(remaining_lessons=0, policy_fixture={
            "version": "fixture_1", "enabled_options": list(
                ("makeup_lesson", "change_tutor", "unused_lessons_refund"))})
        self.assertTrue(all(x["status"] == "NO_REMAINING_LESSONS"
                            for x in r["options"]))
        self.assertTrue(all(not x["shown"] for x in r["options"]))

    def test_dispute_states_are_nonbinding(self):
        for state in ("unverified", "review_pending", "manual_review_recorded"):
            with self.subTest(state=state):
                r = preview(dispute_state=state)
                self.assertTrue(r["manual_review_required"])
                self.assertFalse(r["authenticated_booking_verified"])

    def test_reject_forged_identifiers_and_types(self):
        for bad in ("../case", "a/b", "", "a" * 129, None, 3):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                preview(case_ref=bad)
        for bad in (True, -1, 1001, 1.5, "3"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                preview(remaining_lessons=bad)
        with self.assertRaises(ValueError):
            preview(dispute_state="approved")

    def test_reject_untrusted_policy_fixtures(self):
        for fixture in ({"version": "../bad", "enabled_options": []},
                        {"version": "v1", "enabled_options": ["refund"]},
                        {"version": "v1", "enabled_options": ["makeup_lesson",
                                                              "makeup_lesson"]},
                        {"version": "v1", "enabled_options": [True]},
                        {"version": "v1", "enabled_options": [], "extra": 1},
                        "approved", True):
            with self.subTest(fixture=fixture), self.assertRaises(ValueError):
                preview(policy_fixture=fixture)

    def test_no_real_money_booking_or_payout_flags(self):
        r = preview(policy_fixture={"version": "test", "enabled_options": [
            "makeup_lesson", "change_tutor", "unused_lessons_refund"]})
        for flag in ("policy_approved", "real_money", "refund_executed",
                     "booking_modified", "payout_authorized",
                     "operating_db_connected", "authenticated_booking_verified"):
            self.assertIs(r[flag], False)
        for option in r["options"]:
            for flag in ("student_can_select", "refund_executed",
                         "booking_modified", "teacher_reassigned"):
                self.assertIs(option[flag], False)

    def test_read_only_page_has_three_disabled_actions(self):
        html = pathlib.Path(__file__).with_name("learner-remedy-review.html").read_text(
            encoding="utf-8")
        self.assertEqual(3, html.count('aria-disabled="true"'))
        self.assertEqual(3, html.count("<button "))
        self.assertNotIn("<script", html.lower())
        self.assertNotIn("<form", html.lower())
        self.assertIn("정책 검토 중", html)
        self.assertIn("남은 수업 환불", html)


if __name__ == "__main__":
    unittest.main()
