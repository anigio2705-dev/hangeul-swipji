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

    def test_missing_role_pair_rejected(self):
        data = self.sample("14")
        data["items"][-1]["id"] = "other"
        with self.assertRaises(ValueError):
            validate_artifact(data, "14")

    def test_extra_role_pair_rejected(self):
        data = self.sample("14")
        data["items"].append({"id": "unreviewed_role",
                              "text": "An unapproved fifth introducer role",
                              "expected": "Must be rejected rather than treated as a valid four-role contract"})
        with self.assertRaisesRegex(ValueError, "exactly four referral role pairs"):
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


if __name__ == "__main__":
    unittest.main()
