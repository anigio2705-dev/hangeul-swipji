"""Independent regression tests for non-curated READY developer submissions.

These fixtures never call an AI, touch production, or dispatch a workflow.
"""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from hq_160_task_cycle import contracts
from hq_six_cycle_supervisor import reviewed_dynamic_tests, independent_check


def catalog():
    return contracts("\n".join(f"{n}. [ ] Contract {n}" for n in range(1, 161)))


class DynamicReadySupervisorTests(unittest.TestCase):
    def fixture(self, root, state="READY", review="PASS", source="feature.py"):
        (root / "automation").mkdir(exist_ok=True)
        (root / "feature.py").write_text("def feature(): return True\n", encoding="utf-8")
        (root / "test_feature.py").write_text(
            "import unittest\nclass FeatureTest(unittest.TestCase):\n"
            "    def test_feature(self): self.assertTrue(True)\n", encoding="utf-8")
        record = {"owner": "12", "support": ["13"], "state": state,
                  "source_paths": [source], "test_paths": ["test_feature.py"],
                  "independent_team15": review,
                  "independent_ci_url": "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/123"}
        (root / "automation/hq_semantic_contract_paths.json").write_text(
            json.dumps({"schema": 1, "items": {"45": record}}), encoding="utf-8")
        (root / "automation/task-evidence.json").write_text("{}", encoding="utf-8")
        return record

    def test_only_independently_approved_real_ready_is_eligible(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            record = self.fixture(root)
            self.assertEqual(reviewed_dynamic_tests("12", 45, "feature.py", catalog(), root),
                             ["test_feature.py"])
            self.assertEqual(reviewed_dynamic_tests("13", 45, "feature.py", catalog(), root), [])
            self.assertEqual(reviewed_dynamic_tests("12", 47, "feature.py", catalog(), root), [])
            self.assertEqual(reviewed_dynamic_tests("12", 45, "other.py", catalog(), root), [])
            record["state"] = "CANDIDATE"
            (root / "automation/hq_semantic_contract_paths.json").write_text(
                json.dumps({"schema": 1, "items": {"45": record}}), encoding="utf-8")
            self.assertEqual(reviewed_dynamic_tests("12", 45, "feature.py", catalog(), root), [])
            record["state"] = "READY"
            record["independent_team15"] = "PENDING"
            (root / "automation/hq_semantic_contract_paths.json").write_text(
                json.dumps({"schema": 1, "items": {"45": record}}), encoding="utf-8")
            self.assertEqual(reviewed_dynamic_tests("12", 45, "feature.py", catalog(), root), [])

    def test_fail_closed_for_missing_registry_or_non_unittest_test(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.assertEqual(reviewed_dynamic_tests("12", 45, "feature.py", catalog(), root), [])
            record = self.fixture(root)
            record["test_paths"] = ["test_feature.js"]
            (root / "test_feature.js").write_text("test()", encoding="utf-8")
            (root / "automation/hq_semantic_contract_paths.json").write_text(
                json.dumps({"schema": 1, "items": {"45": record}}), encoding="utf-8")
            self.assertEqual(reviewed_dynamic_tests("12", 45, "feature.py", catalog(), root), [])

    def test_dynamic_commit_runs_trusted_task_specific_regression(self):
        sha = "a" * 40
        def fake_api(path, token):
            if "/branches/" in path:
                return {"commit": {"sha": sha}}
            return {"commit": {"message": "bot(team12): task #45 tested isolated fix to feature.py"},
                    "files": [{"filename": "feature.py"}]}
        calls = []
        def fake_cmd(args, **kwargs):
            calls.append(args)
            return SimpleNamespace(returncode=0, stdout="Ran 1 test in 0.001s\nOK\n", stderr="")
        with patch("hq_six_cycle_supervisor.reviewed_dynamic_tests", return_value=["test_feature.py"]), \
             patch("hq_six_cycle_supervisor.api", side_effect=fake_api), \
             patch("hq_six_cycle_supervisor.cmd", side_effect=fake_cmd):
            verdict, reason, proof = independent_check(
                "12", {"task_number": 45, "path": "feature.py", "commit": sha}, "token", catalog())
        self.assertEqual(verdict, "TEST_PASS_PENDING_CI")
        self.assertIn("test_feature.py", proof["test_command"])
        self.assertTrue(any("unittest" in args and "test_feature.py" in args for args in calls))
        self.assertNotEqual(verdict, "CODE_VERIFIED")

    def test_zero_discovered_tests_are_rejected(self):
        sha = "a" * 40
        def fake_api(path, token):
            if "/branches/" in path:
                return {"commit": {"sha": sha}}
            return {"commit": {"message": "bot(team12): task #45 tested isolated fix to feature.py"},
                    "files": [{"filename": "feature.py"}]}
        def fake_cmd(args, **kwargs):
            output = "Ran 0 tests in 0.001s\nOK\n" if "unittest" in args else ""
            return SimpleNamespace(returncode=0, stdout=output, stderr="")
        with patch("hq_six_cycle_supervisor.reviewed_dynamic_tests", return_value=["test_feature.py"]), \
             patch("hq_six_cycle_supervisor.api", side_effect=fake_api), \
             patch("hq_six_cycle_supervisor.cmd", side_effect=fake_cmd):
            verdict, reason, proof = independent_check(
                "12", {"task_number": 45, "path": "feature.py", "commit": sha}, "token", catalog())
        self.assertEqual(verdict, "RETRY")
        self.assertIn("zero tests", reason)
        self.assertEqual(proof, {})

    def test_wrong_scope_is_rejected_before_github_lookup(self):
        with patch("hq_six_cycle_supervisor.reviewed_dynamic_tests", return_value=[]), \
             patch("hq_six_cycle_supervisor.api") as api:
            verdict, reason, _ = independent_check(
                "13", {"task_number": 47, "path": "phase3/learning.py", "commit": "a"*40},
                "token", catalog())
        self.assertEqual(verdict, "RETRY")
        api.assert_not_called()


if __name__ == "__main__":
    unittest.main()
