import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hq_160_task_cycle import CURATED_TARGETS, contracts
from hq_six_cycle_supervisor import supervise

def sample():
    return "\n".join(f"{n}. [ ] Acceptance criterion {n}" for n in range(1, 161))

class SixTeamSupervisorTests(unittest.TestCase):
    def run_cycle(self, committed=False, verdict="TEST_PASS_PENDING_CI", depth=0, repairs=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "artifacts"
            for team in CURATED_TARGETS:
                target = root / ("team-" + team + "-development")
                target.mkdir(parents=True)
                tasks = ([{"task_number": 109, "path": "phase3/team14_referral_store.py",
                           "status": "committed", "commit": "a" * 40}]
                         if team == "14" and committed else [])
                (target / "team-result.json").write_text(
                    json.dumps({"team": team, "tasks": tasks}), encoding="utf-8")
            output = Path(directory) / "report.json"
            with patch.dict(os.environ, {"GITHUB_REF_NAME": "automation/hq-pilot-13-14-15-20261029"}), \
                 patch("hq_six_cycle_supervisor.load_catalog", return_value=contracts(sample())), \
                 patch("hq_six_cycle_supervisor.independent_check",
                       return_value=(verdict, "Precise fix: assertion 7", {})), \
                 patch("hq_six_cycle_supervisor.four_role_evidence",
                       return_value={"status": "read_four_independent_artifacts"}), \
                 patch("hq_six_cycle_supervisor.api") as api:
                report = supervise(str(root), "dummy", depth, repairs or {}, str(output))
                self.assertTrue(output.exists())
                return report, api

    def test_no_real_progress_stops_without_repeat_dispatch(self):
        report, api = self.run_cycle()
        self.assertFalse(report["dispatched_next"])
        self.assertEqual(report["verified_new_functional_code"], 0)
        api.assert_not_called()

    def test_independently_tested_commit_dispatches_next_bounded_round(self):
        report, api = self.run_cycle(committed=True)
        self.assertTrue(report["dispatched_next"])
        self.assertEqual(report["verified_new_functional_code"], 1)
        self.assertEqual(api.call_args.kwargs["payload"]["inputs"]["chain_depth"], "1")

    def test_precise_failure_retries_once_then_stops(self):
        report, api = self.run_cycle(committed=True, verdict="RETRY")
        self.assertTrue(report["dispatched_next"])
        repair_json = api.call_args.kwargs["payload"]["inputs"]["repair_instructions_json"]
        self.assertIn("assertion 7", json.loads(repair_json)["14"]["109"]["repair_instruction"])
        again, api_again = self.run_cycle(
            committed=True, verdict="RETRY", depth=1,
            repairs={"14": {"109": {"attempts": 1, "repair_instruction": "first failure"}}})
        self.assertFalse(again["dispatched_next"])
        api_again.assert_not_called()

    def test_budget_caps_successful_chains(self):
        report, api = self.run_cycle(committed=True, depth=2)
        self.assertFalse(report["dispatched_next"])
        api.assert_not_called()

if __name__ == "__main__":
    unittest.main()
