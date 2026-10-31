"""B/15 independent QA-only #119: read-only remedy choices never grant rights.

Based on exact product SHA affc2c682690f39da41b9e37ad32d8b601d79b58.
No production code, database, payment, booking or policy changes.
"""
import itertools
import json
import pathlib
import unittest
from html.parser import HTMLParser

from team14_learner_remedy_preview import OPTIONS, remedy_preview


def preview(**overrides):
    args = {"case_ref": "case_119", "remaining_lessons": 3,
            "dispute_state": "review_pending", "policy_fixture": None}
    args.update(overrides)
    return remedy_preview(**args)


class _Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class BQA119RemedyIndependent(unittest.TestCase):
    def assert_never_authorized(self, result):
        self.assertTrue(result["manual_review_required"])
        for flag in ("authenticated_booking_verified", "policy_approved",
                     "real_money", "refund_executed", "booking_modified",
                     "payout_authorized", "operating_db_connected"):
            self.assertIs(result[flag], False, flag)
        self.assertEqual(tuple(x["id"] for x in result["options"]), OPTIONS)
        for opt in result["options"]:
            for flag in ("student_can_select", "refund_executed",
                         "booking_modified", "teacher_reassigned"):
                self.assertIs(opt[flag], False, (opt["id"], flag))

    def test_all_three_remedies_are_read_only_without_policy(self):
        result = preview()
        self.assertEqual([x["status"] for x in result["options"]],
                         ["POLICY_NOT_APPROVED"] * 3)
        self.assertTrue(all(x["shown"] for x in result["options"]))
        self.assertIsNone(result["policy_fixture_version"])
        self.assert_never_authorized(result)

    def test_dispute_state_cannot_upgrade_fixture_to_actual_entitlement(self):
        fixture = {"version": "test_v1", "enabled_options": list(OPTIONS)}
        for state in ("unverified", "review_pending", "manual_review_recorded"):
            with self.subTest(state=state):
                result = preview(dispute_state=state, policy_fixture=fixture)
                self.assertEqual(result["dispute_state"], state)
                self.assertTrue(all(x["status"] == "SIMULATION_ONLY"
                                    for x in result["options"]))
                self.assert_never_authorized(result)

    def test_all_eight_fixture_subsets_are_nonbinding(self):
        for enabled in itertools.chain.from_iterable(
                itertools.combinations(OPTIONS, size) for size in range(4)):
            with self.subTest(enabled=enabled):
                result = preview(policy_fixture={
                    "version": "fixture_only", "enabled_options": list(enabled)})
                for opt in result["options"]:
                    expected = ("SIMULATION_ONLY" if opt["id"] in enabled
                                else "POLICY_NOT_APPROVED")
                    self.assertEqual(opt["status"], expected)
                    self.assertIs(opt["fixture_eligible"], opt["id"] in enabled)
                self.assert_never_authorized(result)

    def test_zero_remaining_lessons_blocks_even_full_fixture(self):
        result = preview(remaining_lessons=0, policy_fixture={
            "version": "v1", "enabled_options": list(OPTIONS)})
        self.assertTrue(all(x["status"] == "NO_REMAINING_LESSONS"
                            and not x["shown"] and not x["fixture_eligible"]
                            for x in result["options"]))
        self.assert_never_authorized(result)

    def test_one_and_max_remaining_lessons_are_still_nonbinding(self):
        for count in (1, 1000):
            with self.subTest(count=count):
                result = preview(remaining_lessons=count, policy_fixture={
                    "version": "v1", "enabled_options": ["unused_lessons_refund"]})
                self.assertEqual(result["remaining_lessons"], count)
                self.assert_never_authorized(result)

    def test_invalid_lesson_counts_fail_closed(self):
        for value in (-100, -1, 1001, 10**100, True, False, 1.0, 2.5,
                      "3", None, [], {}, complex(1, 0)):
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                preview(remaining_lessons=value)

    def test_identifier_path_injection_and_types_rejected(self):
        for value in ("", "../escape", "a/b", "a\\b", "x?y", "x#y",
                      "x;y", "x\nY", "<script>", "a" * 129,
                      None, 1, True, [], {}):
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                preview(case_ref=value)
        self.assertEqual(preview(case_ref="A_z-09")["case_ref"], "A_z-09")

    def test_unknown_dispute_states_cannot_impersonate_approval(self):
        for value in ("approved", "APPROVED", "paid", "auto_refund",
                      "manual_review_recorded ", "", None, 1, True):
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                preview(dispute_state=value)

    def test_malformed_policy_fixture_rejected_without_fallback(self):
        invalid = [
            True, [], "approved", {"version": "v1"},
            {"version": "v1", "enabled_options": [], "approved": True},
            {"version": "../bad", "enabled_options": []},
            {"version": "", "enabled_options": []},
            {"version": "a" * 129, "enabled_options": []},
            {"version": 1, "enabled_options": []},
            {"version": "v1", "enabled_options": "makeup_lesson"},
            {"version": "v1", "enabled_options": [True]},
            {"version": "v1", "enabled_options": [1]},
            {"version": "v1", "enabled_options": ["refund"]},
            {"version": "v1", "enabled_options": ["makeup_lesson"] * 2},
            {"version": "v1", "enabled_options": {"makeup_lesson"}},
        ]
        for value in invalid:
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                preview(policy_fixture=value)

    def test_policy_input_is_not_mutated_and_result_is_json_safe(self):
        fixture = {"version": "fixture", "enabled_options": list(OPTIONS)}
        before = json.dumps(fixture, sort_keys=True)
        result = preview(policy_fixture=fixture)
        self.assertEqual(before, json.dumps(fixture, sort_keys=True))
        self.assertEqual(json.loads(json.dumps(result)), result)
        self.assert_never_authorized(result)

    def test_result_mutation_does_not_poison_later_calls(self):
        first = preview(policy_fixture={
            "version": "v1", "enabled_options": list(OPTIONS)})
        first["options"][0]["student_can_select"] = True
        first["options"].append({"id": "forged"})
        fresh = preview()
        self.assertEqual(len(fresh["options"]), 3)
        self.assert_never_authorized(fresh)

    def test_html_all_buttons_disabled_no_active_input_or_network_tags(self):
        html = pathlib.Path(__file__).with_name(
            "learner-remedy-review.html").read_text(encoding="utf-8")
        parser = _Tags()
        parser.feed(html)
        buttons = [attrs for tag, attrs in parser.tags if tag == "button"]
        self.assertEqual(len(buttons), 3)
        for attrs in buttons:
            self.assertIn("disabled", attrs)
            self.assertEqual(attrs.get("aria-disabled"), "true")
            self.assertEqual(attrs.get("type"), "button")
        forbidden = {"script", "form", "input", "iframe", "object",
                     "embed", "a", "link", "img", "video", "audio"}
        self.assertFalse(forbidden.intersection(tag for tag, _ in parser.tags))
        self.assertIn("남은 수업 환불", html)
        self.assertIn("강사 변경", html)
        self.assertIn("보강 수업", html)

    def test_html_csp_blocks_scripts_and_forms_for_static_preview(self):
        html = pathlib.Path(__file__).with_name(
            "learner-remedy-review.html").read_text(encoding="utf-8")
        parser = _Tags()
        parser.feed(html)
        metas = [attrs for tag, attrs in parser.tags if tag == "meta"]
        policies = [attrs.get("content", "") for attrs in metas
                    if attrs.get("http-equiv", "").lower() ==
                    "content-security-policy"]
        self.assertEqual(len(policies), 1)
        self.assertIn("default-src 'none'", policies[0])
        self.assertIn("form-action 'none'", policies[0])
        self.assertIn("base-uri 'none'", policies[0])
        self.assertNotIn("onclick=", html.lower())


if __name__ == "__main__":
    unittest.main()
