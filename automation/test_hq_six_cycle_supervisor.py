import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hq_160_task_cycle import CURATED_TARGETS, contracts
from hq_six_cycle_supervisor import supervise, promote_prior

def sample():
    return "\n".join(f"{n}. [ ] Acceptance criterion {n}" for n in range(1, 161))

class SixTeamSupervisorTests(unittest.TestCase):
    def run_cycle(self, committed=False, verdict="TEST_PASS_PENDING_CI", depth=0,
                  repairs=None, team="14", task_number=109, task_status="committed",
                  feedback=None, ledger=None):
        self._selected_team = team
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "artifacts"
            for team in CURATED_TARGETS:
                target = root / ("team-" + team + "-development")
                target.mkdir(parents=True)
                path = {"13": "phase3/instant_matching.py",
                        "14": "phase3/team14_referral_store.py"}[self._selected_team]
                tasks = ([{"task_number": task_number, "path": path,
                           "status": task_status, "commit": "a" * 40,
                           "feedback": feedback}]
                         if team == self._selected_team and committed else [])
                (target / "team-result.json").write_text(
                    json.dumps({"team": team, "tasks": tasks}), encoding="utf-8")
            output = Path(directory) / "report.json"
            with patch.dict(os.environ, {"GITHUB_REF_NAME": "automation/hq-pilot-13-14-15-20261029", "GITHUB_RUN_ID": "123"}), \
                 patch("hq_six_cycle_supervisor.load_catalog", return_value=contracts(sample())), \
                 patch("hq_six_cycle_supervisor.independent_check",
                       return_value=(verdict, "Precise fix: assertion 7", {"commit": "a" * 40})), \
                 patch("hq_six_cycle_supervisor.load_ledger", return_value=(ledger if ledger is not None else {}, "a" * 40)), \
                 patch("hq_six_cycle_supervisor.save_ledger", return_value=None), \
                 patch("hq_six_cycle_supervisor.promote_prior", return_value=[]), \
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
        report, api = self.run_cycle(committed=True, team="13", task_number=22)
        self.assertTrue(report["dispatched_next"])
        self.assertEqual(report["verified_new_functional_code"], 1)
        inputs = api.call_args.kwargs["payload"]["inputs"]
        self.assertEqual(inputs["chain_depth"], "1")
        self.assertEqual(json.loads(inputs["teams_json"]), ["13"])

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

    def test_failed_patch_receives_precise_one_time_repair_for_only_failed_team(self):
        report, api = self.run_cycle(
            committed=True, team="13", task_number=22, task_status="blocked",
            feedback="Patch must make one unambiguous real change")
        self.assertEqual(report["verified_new_functional_code"], 0)
        self.assertEqual(report["team_verdicts"]["13"][0]["verdict"], "RETRY")
        self.assertTrue(report["dispatched_next"])
        inputs = api.call_args.kwargs["payload"]["inputs"]
        self.assertEqual(json.loads(inputs["teams_json"]), ["13"])
        repair = json.loads(inputs["repair_instructions_json"])["13"]["22"]
        self.assertEqual(repair["attempts"], 1)
        self.assertIn("exact unique", repair["repair_instruction"])
        again, api_again = self.run_cycle(
            committed=True, team="13", task_number=22, task_status="blocked",
            feedback="Patch must make one unambiguous real change",
            depth=1, repairs={"13": {"22": repair}})
        self.assertFalse(again["dispatched_next"])
        api_again.assert_not_called()

    def test_success_without_next_safe_task_does_not_repeat_dispatch(self):
        report, api = self.run_cycle(committed=True, team="14", task_number=109)
        self.assertFalse(report["dispatched_next"])
        self.assertEqual(report["verified_new_functional_code"], 1)
        api.assert_not_called()

    def test_replayed_sha_does_not_count_as_new_development_or_dispatch(self):
        sha = "a" * 40
        for previous_status in ("in_progress", "code_verified"):
            with self.subTest(previous_status=previous_status):
                ledger = {"22": {"status": previous_status, "commit": sha,
                                  "independent_review": "pass"}}
                report, api = self.run_cycle(
                    committed=True, team="13", task_number=22, ledger=ledger)
                self.assertEqual(report["verified_new_functional_code"], 0)
                self.assertEqual(report["staged_pending_CI"], [])
                self.assertFalse(report["dispatched_next"])
                api.assert_not_called()

    def test_pending_ci_is_not_promoted_until_run_completes_successfully(self):
        url = "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/123"
        ledger = {"109": {"status": "in_progress", "independent_review": "pass",
                          "ci_url": url, "ci_result": "pending"}}
        with patch("hq_six_cycle_supervisor.api", return_value={
            "status": "in_progress", "conclusion": None}):
            self.assertEqual(promote_prior(ledger, "dummy"), [])
            self.assertEqual(ledger["109"]["status"], "in_progress")
        with patch("hq_six_cycle_supervisor.api", return_value={
            "status": "completed", "conclusion": "success"}):
            self.assertEqual(promote_prior(ledger, "dummy"), [109])
            self.assertEqual(ledger["109"]["status"], "code_verified")
            self.assertEqual(ledger["109"]["ci_result"], "success")

    def test_budget_caps_successful_chains(self):
        report, api = self.run_cycle(committed=True, depth=2, team="13", task_number=22)
        self.assertFalse(report["dispatched_next"])
        api.assert_not_called()

if __name__ == "__main__":
    unittest.main()
