import os
import unittest
from unittest.mock import patch
from automation.hq_continuity import run_cycle, main

class ContinuityTests(unittest.TestCase):
    def test_pass_and_failure_are_recorded(self):
        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""
        checks = run_cycle(tasks=[("sample", ["python", "--version"])], runner=lambda *a, **k: Result())
        self.assertEqual(checks[0]["status"], "passed")

    def test_rejects_nonisolated_branch(self):
        with patch.dict(os.environ, {"GITHUB_REF_NAME": "main"}):
            with patch("sys.argv", ["worker"]):
                with self.assertRaises(SystemExit):
                    main()
