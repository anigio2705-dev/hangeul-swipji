import unittest
from pathlib import Path

from hq_160_task_cycle import (
    CURATED_TARGETS, contracts, make_report, next_assignment, verify_submission,
)

def sample():
    return "\n".join(f"{n}. [ ] Criterion for item {n}" for n in range(1, 161))

class HQ160TaskCycleTests(unittest.TestCase):
    def test_real_master_160_criteria_are_mapped_to_6_teams(self):
        source = Path(__file__).parent / "hq_backlog_160.md"
        tasks = contracts(source.read_text(encoding="utf-8"))
        self.assertEqual(list(tasks), list(range(1, 161)))
        self.assertEqual({x["owner"] for x in tasks.values()}, set(CURATED_TARGETS))
        self.assertTrue(all(x["criterion"] and x["evidence_required"] for x in tasks.values()))
        self.assertTrue(all(x["owner"] not in x["support"] for x in tasks.values()))
        self.assertTrue(tasks[154]["external_gate"])
        self.assertTrue(tasks[154]["approval_gate"])
        self.assertIn(151, tasks[154]["dependencies"])
        self.assertEqual(tasks[9]["owner"], "15")

    def test_reject_duplicate_or_missing_item(self):
        with self.assertRaisesRegex(ValueError, "160"):
            contracts(sample() + "\n160. [ ] duplicate")
        with self.assertRaisesRegex(ValueError, "160"):
            contracts(sample().replace("4. [ ]", "5. [ ]"))

    def test_each_team_gets_a_real_scoped_task_and_no_fake_completion(self):
        report = make_report(sample())
        self.assertEqual(report["final_complete"], 0)
        self.assertEqual(len(report["assignments"]), 6)
        for team, assignment in report["assignments"].items():
            self.assertIsNotNone(assignment)
            self.assertEqual(assignment["team"], team)
            self.assertIn(team, [assignment["owner"]] + assignment["support"])
            self.assertIn((assignment["task_number"], assignment["path"]), CURATED_TARGETS[team])
            self.assertEqual(assignment["attempt"], 1)

    def test_code_verified_skips_reimplementation_and_assigns_next(self):
        catalog = contracts(sample())
        task = next_assignment("12", catalog, {"41": {"status": "code_verified"}})
        self.assertEqual(task["task_number"], 52)
        self.assertIsNone(next_assignment("12", catalog, {
            "41": {"status": "code_verified"}, "52": {"status": "code_verified"},
        }))

    def test_failure_feedback_is_specific_and_retry_is_bounded(self):
        catalog = contracts(sample())
        failure = {"8": {"attempts": 1, "repair_instruction": "Fix failed assertion 42"}}
        task = next_assignment("15", catalog, failures=failure)
        self.assertEqual(task["task_number"], 8)
        self.assertEqual(task["mode"], "repair")
        self.assertEqual(task["attempt"], 2)
        self.assertIn("assertion 42", task["repair_instruction"])
        next_task = next_assignment("15", catalog, failures={"8": {"attempts": 2}})
        self.assertEqual(next_task["task_number"], 9)

    def test_independent_verification_not_developer_self_report(self):
        assignment = next_assignment("15", contracts(sample()))
        sha = "a" * 40
        submission = {"commit": sha, "developer_says_passed": True}
        trusted = {
            "branch_head": sha, "changed_files": [assignment["path"]],
            "independent_test": "failure", "test_error": "assertion 42",
            "ci_conclusion": "success",
            "ci_url": "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/123",
        }
        failure = verify_submission(assignment, submission, trusted)
        self.assertEqual(failure["verdict"], "RETRY")
        self.assertIn("assertion 42", failure["repair_instruction"])
        trusted["independent_test"] = "success"
        trusted["ci_conclusion"] = "failure"
        self.assertEqual(verify_submission(assignment, submission, trusted)["verdict"], "RETRY")
        trusted["ci_conclusion"] = "success"
        passed = verify_submission(assignment, submission, trusted)
        self.assertEqual(passed["verdict"], "CODE_VERIFIED")
        self.assertNotEqual(passed["verdict"], "COMPLETE")
        trusted["changed_files"] = ["other.py"]
        self.assertEqual(verify_submission(assignment, submission, trusted)["verdict"], "RETRY")

    def test_final_complete_requires_master_check(self):
        self.assertEqual(make_report(sample(), {"9": {"status": "complete"}})["final_complete"], 0)

if __name__ == "__main__":
    unittest.main()
