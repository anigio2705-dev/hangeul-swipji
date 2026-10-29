"""Regression: a failed or silent six-team runner must leave an honest artifact.

This test executes the exact embedded Python from the isolated workflow, with
subprocess mocked. No API calls, production writes, or real developer jobs.
"""
import json
import os
import pathlib
import subprocess
import tempfile
import textwrap
import unittest
from types import SimpleNamespace
from unittest.mock import patch

WORKFLOW = pathlib.Path(__file__).resolve().parents[1] / ".github/workflows/hq-six-developers.yml"


def embedded_runner():
    text = WORKFLOW.read_text(encoding="utf-8")
    block = text.split("      - name: Run isolated AI developer\n", 1)[1]
    block = block.split("      - name: Save team result\n", 1)[0]
    lines = block.splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "python - <<'PY'")
    end = next(i for i in range(start + 1, len(lines)) if lines[i].strip() == "PY")
    return textwrap.dedent("\n".join(lines[start + 1:end])) + "\n"


class FailedRunnerArtifactTests(unittest.TestCase):
    def run_embedded(self, returncode, stale=False):
        code = embedded_runner()
        with tempfile.TemporaryDirectory() as directory:
            artifact = pathlib.Path(directory) / "team-result.json"
            if stale:
                artifact.write_text(json.dumps({
                    "team": "11", "calls": 1,
                    "tasks": [{"task_number": 11, "status": "committed"}]
                }), encoding="utf-8")
            original_path = pathlib.Path

            def remap(value):
                return artifact if str(value) == "/tmp/team-result.json" else original_path(value)

            with patch.object(subprocess, "run", return_value=SimpleNamespace(returncode=returncode)) as runner, \
                 patch.object(pathlib, "Path", side_effect=remap), \
                 patch.dict(os.environ, {"HQ_TEAM": "11"}):
                exec(compile(code, "<isolated-workflow-runner>", "exec"), {"__name__": "__main__"})
            runner.assert_called_once()
            return json.loads(artifact.read_text(encoding="utf-8"))

    def test_nonzero_runner_retains_blocked_evidence(self):
        result = self.run_embedded(returncode=1)
        self.assertEqual(result["team"], "11")
        self.assertEqual(result["calls"], 0)
        self.assertEqual(result["committed"], 0)
        self.assertEqual(result["rounds"][0]["status"], "BLOCKED")
        self.assertEqual(result["rounds"][0]["reason"], "runner_failed_or_result_missing")

    def test_stale_previous_result_is_not_counted_as_new_commit(self):
        result = self.run_embedded(returncode=0, stale=True)
        self.assertEqual(result["committed"], 0)
        self.assertEqual(result["calls"], 0)
        self.assertEqual(result["rounds"][0]["status"], "BLOCKED")
        self.assertEqual(result["rounds"][0]["reason"], "runner_failed_or_result_missing")


if __name__ == "__main__":
    unittest.main()
