"""Offline safety tests for six-team candidate artifact generation."""
import unittest
from hq_six_candidate_artifacts import TEAM_TASKS, validate_artifact, generated_python_cache


class CandidateArtifactTests(unittest.TestCase):
    def sample(self, team):
        number, minimum, _ = TEAM_TASKS[team]
        ids = {
            "14": ["teacher_teacher", "teacher_student", "student_teacher", "student_student"],
            "16": ["ko", "en", "ja", "es", "zh", "ru", "mn", "vi"],
        }.get(team, ["case_" + str(i) for i in range(minimum)])
        return {"team": team, "task_number": number, "items": [
            {"id": name, "text": "A concrete sample case " + name,
             "expected": "The safe expected result for " + name}
            for name in ids]}

    def test_each_team_accepts_valid_schema(self):
        for team in TEAM_TASKS:
            with self.subTest(team=team):
                self.assertTrue(validate_artifact(self.sample(team), team))

    def test_only_untracked_python_cache_paths_are_eligible(self):
        self.assertTrue(generated_python_cache("automation/__pycache__/runner.cpython-311.pyc"))
        self.assertTrue(generated_python_cache("phase3/__pycache__/test_a.pyc"))
        self.assertFalse(generated_python_cache("phase3/booking.py"))
        self.assertFalse(generated_python_cache("../__pycache__/runner.pyc"))
        self.assertFalse(generated_python_cache("/tmp/__pycache__/runner.pyc"))
        self.assertFalse(generated_python_cache("phase3/__pycache__/private.txt"))

    def test_wrong_team_rejected(self):
        data = self.sample("12")
        data["team"] = "13"
        with self.assertRaises(ValueError):
            validate_artifact(data, "12")

    def test_missing_required_locale_rejected(self):
        data = self.sample("16")
        data["items"][-1]["id"] = "fr"
        with self.assertRaises(ValueError):
            validate_artifact(data, "16")

    def test_team14_prompt_requires_distinct_person_acceptance_and_negative_cases(self):
        goal = TEAM_TASKS["14"][2].lower()
        self.assertIn("two distinct person identities", goal)
        self.assertIn("valid acceptance", goal)
        self.assertIn("self-identity and cyclic introductions are rejected", goal)
        self.assertIn("do not reject merely because both people have the same role", goal)

    def test_missing_role_pair_rejected(self):
        data = self.sample("14")
        data["items"][-1]["id"] = "other"
        with self.assertRaises(ValueError):
            validate_artifact(data, "14")

    def test_duplicate_case_rejected(self):
        data = self.sample("11")
        data["items"][-1]["id"] = data["items"][0]["id"]
        with self.assertRaises(ValueError):
            validate_artifact(data, "11")

    def test_secret_text_rejected(self):
        data = self.sample("15")
        data["items"][0]["text"] = "Authorization Bearer token"
        with self.assertRaises(ValueError):
            validate_artifact(data, "15")

    def test_unexpected_keys_rejected(self):
        data = self.sample("12")
        data["state"] = "READY"
        with self.assertRaises(ValueError):
            validate_artifact(data, "12")



from hq_six_candidate_semantic_review import semantic_review_flags


class CandidateSemanticRedFlagTests(unittest.TestCase):
    def test_stale_warning_override_is_not_fail_closed(self):
        data = {"team": "11", "items": [{"id": "stale_checkout",
            "text": "stale checkout", "expected": "default behavior is warning without blocking"}]}
        self.assertIn(("stale_checkout", "stale_checkout_must_block"),
                      semantic_review_flags(data))

    def test_safe_stale_block_not_flagged(self):
        data = {"team": "11", "items": [{"id": "stale_checkout",
            "text": "stale checkout", "expected": "Block until branch is refreshed"}]}
        self.assertEqual([], semantic_review_flags(data))

    def test_topic_particle_and_unspecified_number_flagged(self):
        data = {"team": "12", "items": [
            {"id": "topic", "text": "저는 학생입니다", "expected": "The 는 particle marks the subject."},
            {"id": "one", "text": "What is the Korean word for the number 'one'?",
             "expected": "하나"}]}
        self.assertEqual(2, len(semantic_review_flags(data)))

    def test_role_equality_is_not_same_identity(self):
        data = {"team": "14", "items": [{"id": "teacher_teacher",
            "text": "another teacher", "expected": "Reject because same teacher role"}]}
        self.assertIn(("teacher_teacher", "role_equality_is_not_identity"),
                      semantic_review_flags(data))

    def test_recording_without_consent_flagged(self):
        data = {"team": "15", "items": [{"id": "record", "text": "Record session",
            "expected": "Audio is recorded securely"}]}
        self.assertIn(("record", "recording_without_consent_condition"),
                      semantic_review_flags(data))

    def test_localization_requires_source_grounding(self):
        self.assertIn(("*", "localized_labels_need_exact_source_mapping"),
                      semantic_review_flags({"team": "16", "items": []}))


if __name__ == "__main__":
    unittest.main()
