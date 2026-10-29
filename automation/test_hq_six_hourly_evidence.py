"""Fail-closed tests for last-hour bot development classification."""
import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hq_six_team_audit import evaluate, changed_product_files

NOW = datetime(2026, 10, 30, 0, 0, tzinfo=timezone.utc)
SHA = "a" * 40


def commit(files, age_minutes=5, timestamp=True):
    when = NOW - timedelta(minutes=age_minutes)
    data = {"files": [{"filename": p} for p in files]}
    if timestamp:
        data["commit"] = {"committer": {"date": when.isoformat()}}
    return data


def run(conclusion):
    return {"head_sha": SHA, "conclusion": conclusion, "html_url": "https://github.com/example/actions/runs/1"}


def verdict(files, age=5, conclusion="success", timestamp=True):
    return evaluate("12", "automation/hq-team-12-autodev-20261029", SHA,
                    [run(conclusion)], commit(files, age, timestamp), now=NOW)


class HourlyEvidenceTests(unittest.TestCase):
    def test_stale_success_cannot_be_counted_as_current_work(self):
        x = verdict(["phase3/learning.py"], age=70)
        self.assertEqual(x["verdict"], "STALE")
        self.assertFalse(x["last_hour_commit"])
        self.assertEqual(x["actual_ai_calls"], None)

    def test_json_candidate_is_not_product_development(self):
        x = verdict(["automation/candidates/team12-task45.json"])
        self.assertEqual(x["verdict"], "ARTIFACT_ONLY")
        self.assertEqual(x["product_source_paths"], [])
        self.assertEqual(x["full_autonomous_cycle"], "NOT_PROVEN")

    def test_green_ci_and_source_diff_require_human_independent_review(self):
        x = verdict(["phase3/learning.py"])
        self.assertEqual(x["verdict"], "REVIEW")
        self.assertEqual(x["independent_qa"], "UNKNOWN")
        self.assertEqual(x["next_task_handoff"], "UNKNOWN")

    def test_failed_ci_requires_repair_not_pass(self):
        self.assertEqual(verdict(["phase3/learning.py"], conclusion="failure")["verdict"], "REWORK")

    def test_missing_timestamp_is_unknown_not_fail(self):
        self.assertEqual(verdict(["phase3/learning.py"], timestamp=False)["verdict"], "UNKNOWN")

    def test_test_and_report_only_diff_is_not_product(self):
        files = ["automation/test_hq_six_developers.py", "scripts/team12_server_progress.test.js",
                 "docs/REPORT.md", ".github/workflows/check.yml"]
        self.assertEqual(changed_product_files(commit(files)), [])

    def test_future_timestamp_outside_clock_tolerance_is_stale(self):
        self.assertEqual(verdict(["phase3/learning.py"], age=-10)["verdict"], "STALE")

    def test_exact_sha_only_matches_relevant_ci(self):
        x = evaluate("12", "b", SHA, [{"head_sha": "b" * 40, "conclusion": "success"}],
                     commit(["phase3/learning.py"]), now=NOW)
        self.assertEqual(x["verdict"], "UNVERIFIED")
        self.assertEqual(x["passing_runs"], [])


if __name__ == "__main__":
    unittest.main()
