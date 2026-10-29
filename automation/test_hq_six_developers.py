import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from hq_six_developers import apply_patch, validate_candidate, choose_work_items, run_checks
from hq_160_task_cycle import _semantic_dispatch_gate, contracts

class BoundedPatchTests(unittest.TestCase):
    def test_runner_must_reject_unreviewed_semantic_task_even_if_ledger_is_stale(self):
        self.assertFalse(_semantic_dispatch_gate(51, 'scripts/audit-hangul-audio.py'))
        self.assertFalse(_semantic_dispatch_gate(22, 'phase3/instant_matching.py'))

    def test_reviewed_ready_reaches_actual_six_team_runner(self):
        c = contracts("\n".join(f"{i}. [ ] Item {i}" for i in range(1, 161)))
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "feature.py").write_text("def feature(): return True\n")
            (root / "test_feature.py").write_text("import unittest\nclass TestFeature(unittest.TestCase):\n def test_feature(self): self.assertTrue(True)\n")
            record = {"owner": "12", "state": "READY",
                      "source_paths": ["feature.py"], "test_paths": ["test_feature.py"],
                      "independent_team15": "PASS",
                      "independent_ci_url": "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/123"}
            reg = {"schema": 1, "items": {"45": record}}
            chosen = choose_work_items("12", c, {}, {}, reg, root)
            self.assertEqual(len(chosen), 1)
            self.assertEqual(chosen[0]["number"], 45)
            self.assertTrue(chosen[0]["dynamic"])
            self.assertEqual(chosen[0]["tests"], ["test_feature.py"])
            self.assertEqual(chosen[0]["unsupported_reason"], "")
            self.assertFalse(any(x["dynamic"] for x in choose_work_items("13", c, {}, {}, reg, root)))
            # HTML tasks must never be passed to the Python AST patch runner.
            (root / "feature.html").write_text("<html></html>")
            record["source_paths"] = ["feature.html"]
            blocked = choose_work_items("12", c, {}, {}, reg, root)
            self.assertIn("non-Python", blocked[0]["unsupported_reason"])

    def test_unsupported_ready_does_not_starve_next_safe_ready(self):
        c = contracts("\n".join(f"{i}. [ ] Item {i}" for i in range(1, 161)))
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "page.html").write_text("<html><body>lesson</body></html>")
            (root / "feature.py").write_text("def feature(): return True\n")
            (root / "test_feature.py").write_text(
                "import unittest\nclass TestFeature(unittest.TestCase):\n"
                " def test_feature(self): self.assertTrue(True)\n")
            def entry(path):
                return {"owner": "12", "state": "READY",
                        "source_paths": [path], "test_paths": ["test_feature.py"],
                        "independent_team15": "PASS",
                        "independent_ci_url": "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/123"}
            reg = {"schema": 1, "items": {"45": entry("page.html"),
                                          "46": entry("feature.py")}}
            chosen = choose_work_items("12", c, {}, {}, reg, root)
            self.assertEqual(chosen[0]["number"], 46)
            self.assertEqual(chosen[0]["path"], "feature.py")
            self.assertEqual(chosen[0]["unsupported_reason"], "")
            self.assertEqual(reg["items"]["45"]["state"], "READY",
                             "The original independently reviewed registry must remain immutable")
            # When no Python READY exists, preserve a truthful unsupported
            # diagnostic rather than fabricating an AI call.
            del reg["items"]["46"]
            blocked = choose_work_items("12", c, {}, {}, reg, root)
            self.assertEqual(blocked[0]["number"], 45)
            self.assertIn("non-Python", blocked[0]["unsupported_reason"])

    def test_ready_task_specific_unittest_cannot_pass_with_zero_tests(self):
        fake = SimpleNamespace(returncode=0, stdout="", stderr="Ran 0 tests in 0.000s\nOK\n")
        with patch("hq_six_developers.shell", return_value=fake):
            ok, message = run_checks("12", "feature.py", ["test_feature.py"])
        self.assertFalse(ok)
        self.assertIn("Ran 0 tests", message)

    def test_single_unique_patch_and_valid_python(self):
        original = "def calculate_total(value):\n    return value + 1\n" + ("# meaningful existing code context\n" * 5)
        changed = apply_patch(original, {
            "old": "return value + 1",
            "new": "return value + 2",
            "reason": "fix arithmetic",
        })
        self.assertIn("return value + 2", changed)
        validate_candidate(original, changed, "example.py")

    def test_ambiguous_or_null_patch_rejected(self):
        original = "def a():\n    return 123\ndef b():\n    return 123\n"
        with self.assertRaisesRegex(ValueError, "unambiguous"):
            apply_patch(original, {"old": "    return 123", "new": "    return 456"})
        with self.assertRaisesRegex(ValueError, "Null"):
            apply_patch(original, {"old": "def a():\n    return 123",
                                   "new": "def a():\n    return '" + chr(0) + "'"})

    def test_team15_collision_gate_cannot_be_weakened_by_ai(self):
        original = ("changes = {'11': {'shared.py'}, '13': {'shared.py'}}\n"
                    "failures = []\n"
                    "common = ['shared.py']\n"
                    "if common:\n"
                    "    failures.append('overlap')\n"
                    "# preserve existing verification\n")
        weakened = original.replace(
            "    failures.append('overlap')",
            "    if 'shared.py' in []:\n        failures.append('overlap')")
        with self.assertRaisesRegex(ValueError, "Collision gate weakening forbidden"):
            validate_candidate(original, weakened, "scripts/team15_independent_gate.py")
        safe = original.replace("# preserve existing verification",
                                "# preserve existing verification and audit every collision")
        validate_candidate(original, safe, "scripts/team15_independent_gate.py")

    def test_truncated_or_whole_file_patch_rejected(self):
        with self.assertRaisesRegex(ValueError, "large"):
            apply_patch("x" * 10000, {"old": "x" * 5000, "new": "y" * 5000})
        with self.assertRaisesRegex(ValueError, "unambiguous"):
            apply_patch("def a():\n    return 123\n", {
                "old": "def a():\n    return 123",
                "new": "def a():\n    return 123"})

    def test_workflow_retry_never_reuses_stale_results_or_crashes_on_os(self):
        """The actual GitHub inline runner must preserve truthful six-team evidence."""
        import ast
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/hq-six-developers.yml").read_text(encoding="utf-8")
        self.assertIn("  push:\n    branches:\n      - automation/hq-pilot-13-14-15-20261029", workflow)
        self.assertIn("      - 'automation/hq_semantic_contract_paths.json'", workflow)
        heredoc = workflow.split("          python - <<'PY'\n", 1)[1].split("\n          PY", 1)[0]
        script = "\n".join(line[10:] if line.startswith("          ") else line
                           for line in heredoc.splitlines())
        parsed = ast.parse(script)
        imports = {alias.name for node in parsed.body if isinstance(node, ast.Import)
                   for alias in node.names}
        self.assertIn("os", imports, "A failed runner must not crash while recording BLOCKED")
        self.assertIn('result_file = pathlib.Path("/tmp/team-result.json")', script)
        self.assertIn("result_file.unlink(missing_ok=True)", script)
        self.assertLess(script.index("result_file.unlink(missing_ok=True)"),
                        script.index('subprocess.run(["python", "/tmp/hq_six_developers.py"])'))
        self.assertIn('"reason": "runner_failed_or_result_missing"', script)
        self.assertIn('pathlib.Path("/tmp/team-result.json").write_text', script)

if __name__ == "__main__":
    unittest.main()
