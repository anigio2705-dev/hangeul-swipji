"""Regression tests for the real-agent handoff; no fake AI success claims."""
import os
import tempfile
import unittest
from unittest.mock import patch
from ai_agent_runner import run_once
from continuous_dispatcher import MARKER
from work_request_worker import DurableWorkStore


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = DurableWorkStore(os.path.join(self.temp.name, "worker.db"))
        self.store.ingest({"number": 301, "title": MARKER + " Test task", "state": "open"})
        self.git_sha = "a" * 40

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def git(self, cmd, cwd=None, capture_output=None, text=None, check=None):
        from subprocess import CompletedProcess
        if cmd[-1] == "--show-current":
            return CompletedProcess(cmd, 0, "work/isolated\n", "")
        if cmd[-1] == "HEAD":
            return CompletedProcess(cmd, 0, self.git_sha + "\n", "")
        raise AssertionError(cmd)

    def test_missing_auth_does_not_invoke_agent(self):
        with patch("ai_agent_runner.subprocess.run", side_effect=self.git) as call:
            with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
                result = run_once(self.store, workdir=self.temp.name)
        self.assertEqual(result["status"], "BLOCKED_AUTH")
        self.assertEqual(call.call_count, 2)

    def test_successful_process_without_commit_is_not_success(self):
        def runner(cmd, **kwargs):
            from subprocess import CompletedProcess
            if cmd[0] == "codex":
                return CompletedProcess(cmd, 0, "done", "")
            return self.git(cmd, **kwargs)
        with patch("ai_agent_runner.subprocess.run", side_effect=runner):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-only"}):
                result = run_once(self.store, workdir=self.temp.name)
        self.assertEqual(result["status"], "NO_COMMIT")
        self.assertNotEqual(self.store.snapshot(301)["status"], "REPORTED")

    def test_commit_changes_report_qa_pending_not_ready(self):
        calls = [0]
        def runner(cmd, **kwargs):
            from subprocess import CompletedProcess
            if cmd[0] == "codex":
                calls[0] += 1
                return CompletedProcess(cmd, 0, "done", "")
            if cmd[-1] == "HEAD" and calls[0]:
                return CompletedProcess(cmd, 0, "b" * 40 + "\n", "")
            return self.git(cmd, **kwargs)
        with patch("ai_agent_runner.subprocess.run", side_effect=runner):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-only"}):
                result = run_once(self.store, workdir=self.temp.name)
        self.assertEqual(result["status"], "REPORTED_QA_PENDING")
        self.assertEqual(self.store.snapshot(301)["status"], "REPORTED")


if __name__ == "__main__":
    unittest.main()
