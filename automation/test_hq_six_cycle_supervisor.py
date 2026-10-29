import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hq_160_task_cycle import CURATED_TARGETS, contracts
from hq_six_cycle_supervisor import supervise, promote_prior, REGRESSIONS, independent_check

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
                       return_value=(verdict, "Precise fix: assertion 7", {"commit": "a" * 40, "test_command": "python -m unittest discover -s phase3 -p test_global_learning.py"})), \
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

    def test_independently_tested_commit_stops_if_no_next_safe_task(self):
        report, api = self.run_cycle(committed=True, team="13", task_number=22)
        self.assertFalse(report["dispatched_next"])
        self.assertEqual(report["verified_new_functional_code"], 1)
        api.assert_not_called()

    def test_precise_failure_without_independent_ready_stops_safely(self):
        report, api = self.run_cycle(committed=True, verdict="RETRY")
        self.assertFalse(report["dispatched_next"])
        self.assertEqual(report["team_verdicts"]["14"][0]["verdict"], "RETRY")
        self.assertIn("no safe new assignment", report["next_reason"])
        api.assert_not_called()
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
        # The failure is diagnosed, but the historical curated target cannot
        # bypass the independent READY registry just to spend another API call.
        self.assertFalse(report["dispatched_next"])
        api.assert_not_called()
        repair = {"attempts": 1, "repair_instruction":
                  "Copy an exact unique source fragment; previous patch was rejected"}
        ledger = {}
        again, api_again = self.run_cycle(
            committed=True, team="13", task_number=22, task_status="blocked",
            feedback="Patch must make one unambiguous real change",
            depth=1, repairs={"13": {"22": repair}}, ledger=ledger)
        self.assertEqual(ledger["22"]["status"], "blocked")
        self.assertEqual(ledger["22"]["repair_attempts"], 1)
        self.assertFalse(again["dispatched_next"])
        self.assertEqual(again["dispatched_teams"], [])
        api_again.assert_not_called()
        # #47 was a wrong-file mapping and must not be the next AI assignment.
        self.assertNotIn("22", str(again["staged_pending_CI"]))

    def test_replayed_exhausted_block_does_not_trigger_next_dispatch_again(self):
        ledger = {"22": {"status": "blocked", "owner": "13",
                         "block_reason": "Previously exhausted repair"}}
        report, api = self.run_cycle(
            committed=True, team="13", task_number=22, task_status="blocked",
            feedback="Patch must make one unambiguous real change",
            repairs={"13": {"22": {"attempts": 1,
                                    "repair_instruction": "Already retried"}}},
            ledger=ledger)
        self.assertFalse(report["dispatched_next"])
        self.assertEqual(ledger["22"]["block_reason"], "Previously exhausted repair")
        api.assert_not_called()

    def test_exhausted_repair_without_safe_followup_stops_and_persists_block(self):
        ledger = {}
        report, api = self.run_cycle(
            committed=True, team="14", task_number=109, task_status="blocked",
            feedback="Regression or unexpected changes: assertion 403 != 200",
            repairs={"14": {"109": {"attempts": 1,
                                     "repair_instruction": "First exact regression fix"}}},
            ledger=ledger)
        self.assertEqual(ledger["109"]["status"], "blocked")
        self.assertFalse(report["dispatched_next"])
        api.assert_not_called()

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
                          "task_specific_verified": True,
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

    def test_wrong_scope_placement_patch_cannot_pass_backlog_47(self):
        verdict, reason, evidence = independent_check(
            "13", {"task_number": 47, "path": "phase3/learning.py",
                   "commit": "a" * 40}, "unused", contracts(sample()))
        self.assertEqual(verdict, "RETRY")
        self.assertIn("valid assigned backlog number", reason)
        self.assertEqual(evidence, {})

    def test_wrong_scope_47_not_available_for_team13_dispatch(self):
        self.assertNotIn((47, "phase3/learning.py"), CURATED_TARGETS["13"])
        self.assertIn("test_instant_matching.py", REGRESSIONS[("13", 22)])

    def test_unrelated_green_ci_never_promotes_task_without_specific_test(self):
        ledger = {"47": {"status": "in_progress", "independent_review": "pass",
                         "ci_url": "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/123",
                         "ci_result": "pending"}}
        with patch("hq_six_cycle_supervisor.api") as api:
            self.assertEqual(promote_prior(ledger, "dummy"), [])
            api.assert_not_called()
        self.assertEqual(ledger["47"]["status"], "in_progress")

    def test_budget_caps_successful_chains(self):
        report, api = self.run_cycle(committed=True, depth=2, team="13", task_number=22)
        self.assertFalse(report["dispatched_next"])
        api.assert_not_called()

    def test_reviewed_dynamic_ready_requires_live_exact_sha_and_real_regression(self):
        """A reviewed #101 READY patch must reach independent tests, not the curated-only rejection."""
        from types import SimpleNamespace
        c = contracts(sample())
        target = "phase3/team14_referral_scenarios.py"
        regression = "phase3/test_team14_referral_scenarios.py"
        new_sha, baseline_sha = "a" * 40, "b" * 40
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "phase3").mkdir()
            (root / target).write_text("def review(): return True\n")
            (root / regression).write_text(
                "import unittest\nclass TestReview(unittest.TestCase):\n"
                " def test_review(self): self.assertTrue(True)\n")
            entry = {"owner": "14", "support": ["15"], "state": "READY",
                     "source_paths": [target], "test_paths": [regression],
                     "independent_team15": "PASS",
                     "independent_ci_url":
                         "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/123",
                     "independent_ci_sha": baseline_sha}
            registry = {"schema": 1, "items": {"101": entry}}
            paths = []
            def fake_api(path, token, method="GET", payload=None, raw=False):
                paths.append(path)
                if path.startswith("/actions/runs/"):
                    return {"head_sha": baseline_sha, "status": "completed",
                            "conclusion": "success"}
                if path.startswith("/branches/"):
                    return {"commit": {"sha": new_sha}}
                if path.startswith("/commits/"):
                    return {"files": [{"filename": target}],
                            "commit": {"message": "bot(team14): task #101 tested isolated fix"}}
                raise AssertionError("Unexpected API path: " + path)
            checked_commands = []
            def fake_cmd(args, cwd=None, timeout=120):
                checked_commands.append(args)
                return SimpleNamespace(returncode=0,
                                       stdout="Ran 1 test in 0.001s\nOK\n",
                                       stderr="")
            task = {"task_number": 101, "path": target, "commit": new_sha}
            with patch("hq_six_cycle_supervisor.api", side_effect=fake_api), \
                 patch("hq_six_cycle_supervisor.cmd", side_effect=fake_cmd):
                verdict, reason, evidence = independent_check(
                    "14", task, "token", c, registry=registry, root=root)
                self.assertEqual(verdict, "TEST_PASS_PENDING_CI", reason)
                self.assertIn(Path(regression).name, evidence["test_command"])
                self.assertIn(str(Path(regression).parent), evidence["test_command"])
                self.assertTrue(any(regression in cmd for cmd in checked_commands))
                self.assertTrue(any(p.startswith("/actions/runs/") for p in paths))
                entry["independent_ci_sha"] = "c" * 40
                verdict, reason, _ = independent_check(
                    "14", task, "token", c, registry=registry, root=root)
                self.assertEqual(verdict, "RETRY")
                self.assertIn("CI", reason)
                entry["independent_ci_sha"] = baseline_sha
                entry["independent_team15"] = "PENDING"
                verdict, reason, _ = independent_check(
                    "14", task, "token", c, registry=registry, root=root)
                self.assertEqual(verdict, "RETRY")
                self.assertIn("READY", reason)

if __name__ == "__main__":
    unittest.main()
