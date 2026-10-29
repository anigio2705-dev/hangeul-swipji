"""Negative/positive tests for honest six-team READY intake diagnostics."""
import unittest
from unittest.mock import patch
from hq_six_candidate_preflight import summarize


def sample_queue(team="11", task=11):
    return {
        "mapped_total": 24, "dispatchable_total": 0,
        "candidate_supply": {
            t: ([{
                "task": task, "blockers": ["team15_independent_review_pending"],
                "unmet_acceptance": ["Real deployment proof required"],
            }] if t == team else [])
            for t in ("11", "12", "13", "14", "15", "16")
        },
    }


class SixTeamReadyIntakeTests(unittest.TestCase):
    def test_all_six_teams_reported_without_fake_ready(self):
        reg = {"items": {"11": {
            "source_paths": ["phase3/staging_server.py"],
            "test_paths": ["phase3/test_staging.py"],
            "independent_team15": "PENDING",
        }}}
        with patch("hq_six_candidate_preflight.readiness", return_value=sample_queue()):
            report = summarize({}, {}, reg, ".")
        self.assertEqual(set(report["teams"]), {"11", "12", "13", "14", "15", "16"})
        self.assertEqual(report["dispatchable_total"], 0)
        self.assertFalse(report["teams"]["11"]["candidates"][0]["ready"])
        self.assertIn("exact_sha_independent_ci_missing", report["teams"]["11"]["next_blockers"])
        self.assertEqual(report["teams"]["13"]["next_blockers"], ["no_mapped_candidate"])

    def test_html_candidate_cannot_be_sent_to_python_patch_runner(self):
        reg = {"items": {"143": {
            "source_paths": ["global-language.js"],
            "test_paths": ["automation/verify_task143.cjs"],
            "independent_ci_url": "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/1",
        }}}
        with patch("hq_six_candidate_preflight.readiness", return_value=sample_queue("16", 143)):
            report = summarize({}, {}, reg, ".")
        blockers = report["teams"]["16"]["next_blockers"]
        self.assertIn("current_python_runner_cannot_edit_target", blockers)
        self.assertIn("independent_python_unittest_missing", blockers)

    def test_team15_cannot_independently_approve_its_own_candidate(self):
        reg = {"items": {"151": {
            "source_paths": ["scripts/team15_independent_gate.py"],
            "test_paths": ["scripts/test_team15_independent_gate.py"],
            "independent_ci_url": "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/1",
        }}}
        with patch("hq_six_candidate_preflight.readiness", return_value=sample_queue("15", 151)):
            report = summarize({}, {}, reg, ".")
        self.assertIn("team15_own_task_requires_external_independent_qa",
                      report["teams"]["15"]["next_blockers"])
        self.assertFalse(report["teams"]["15"]["candidates"][0]["ready"])

    def test_multifile_candidate_requires_explicit_editable_path(self):
        reg = {"items": {"23": {
            "source_paths": ["phase3/instant_matching.py", "phase3/instant-speaking.html"],
            "test_paths": ["phase3/test_instant_matching.py"],
        }}}
        with patch("hq_six_candidate_preflight.readiness", return_value=sample_queue("13", 23)):
            report = summarize({}, {}, reg, ".")
        self.assertIn("single_editable_path_missing", report["teams"]["13"]["next_blockers"])


if __name__ == "__main__":
    unittest.main()
