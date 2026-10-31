"""Isolated fake-Codex subprocess integration tests; NEVER a real API/QA approval."""
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from ai_agent_runner import (DeliveryBlocked, _origin_remote_status, _run_with_lease,
                             ensure_draft_pr, run_once)
from continuous_dispatcher import MARKER
from work_request_worker import DurableWorkStore


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.workdir = root / "worktree"
        self.remote = root / "remote.git"
        self.workdir.mkdir()
        subprocess.run(["git", "init", "--bare", "-q", str(self.remote)], check=True)
        subprocess.run(["git", "init", "-q", str(self.workdir)], check=True)
        self.git(["config", "user.email", "fake-agent@example.invalid"])
        self.git(["config", "user.name", "Fake QA Agent"])
        (self.workdir / "baseline.txt").write_text("baseline")
        self.git(["add", "baseline.txt"])
        self.git(["commit", "-qm", "initial"])
        self.git(["checkout", "-qb", "work/qa-sim"])
        self.git(["remote", "add", "origin", str(self.remote)])
        self.store = DurableWorkStore(str(root / "worker.db"))
        self.store.ingest({"number": 301, "title": MARKER + " Test task", "state": "open"})

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def git(self, args):
        return subprocess.run(["git", *args], cwd=self.workdir, check=True,
                              capture_output=True, text=True)

    def invoke(self, agent_command=("missing-fake-cli-xyz",), *, auth="test-only", store=None,
               remote_url="https://github.com/anigio2705-dev/hangeul-swipji.git",
               timeout=30, heartbeat_interval=5):
        original_run = subprocess.run

        def route(cmd, **kwargs):
            if cmd in (["git", "remote", "get-url", "origin"],
                       ["git", "remote", "get-url", "--all", "origin"]):
                return subprocess.CompletedProcess(cmd, 0, remote_url + "\n", "")
            if cmd == ["git", "remote", "get-url", "--push", "--all", "origin"]:
                configured = original_run(
                    ["git", "config", "--get-all", "remote.origin.pushurl"],
                    cwd=self.workdir, capture_output=True, text=True)
                if configured.returncode == 0:
                    return original_run(cmd, **kwargs)
                return subprocess.CompletedProcess(cmd, 0, remote_url + "\n", "")
            return original_run(cmd, **kwargs)

        with patch("ai_agent_runner.subprocess.run", side_effect=route):
            with patch.dict(os.environ, {"OPENAI_API_KEY": auth,
                                         "GITHUB_REPOSITORY": "anigio2705-dev/hangeul-swipji"}):
                return run_once(store or self.store, workdir=str(self.workdir),
                                agent_command=agent_command, timeout=timeout,
                                heartbeat_interval=heartbeat_interval)

    def test_long_timeout_rejected_before_agent_call(self):
        result = self.invoke((sys.executable, "-c", "pass"), timeout=3600)
        self.assertEqual(result["status"], "UNSAFE_TIMEOUT")
        self.assertNotEqual(self.store.snapshot(301)["status"], "REPORTED")

    def test_missing_auth_never_invokes_cli(self):
        result = self.invoke(auth="")
        self.assertEqual(result["status"], "BLOCKED_AUTH")
        self.assertNotEqual(self.store.snapshot(301)["status"], "REPORTED")

    def test_missing_cli_fails_closed(self):
        result = self.invoke()
        self.assertEqual(result["status"], "AGENT_ERROR")
        self.assertNotEqual(self.store.snapshot(301)["status"], "REPORTED")

    def test_idle_does_not_require_auth(self):
        other = DurableWorkStore(str(Path(self.temp.name) / "empty.db"))
        try:
            self.assertEqual(self.invoke(store=other, auth="")["status"], "IDLE")
        finally:
            other.close()

    def test_zero_exit_without_commit_is_not_success(self):
        result = self.invoke((sys.executable, "-c", "pass"))
        self.assertEqual(result["status"], "NO_COMMIT")
        self.assertNotEqual(self.store.snapshot(301)["status"], "REPORTED")

    def test_dirty_worktree_is_rejected_before_claim(self):
        (self.workdir / "untracked.txt").write_text("not clean")
        self.assertEqual(self.invoke()["status"], "DIRTY_WORKTREE")
        self.assertEqual(self.store.snapshot(301)["status"], "PENDING")

    def test_main_branch_is_rejected(self):
        self.git(["checkout", "-qb", "main"])
        self.assertEqual(self.invoke()["status"], "UNSAFE_BRANCH")
        self.assertEqual(self.store.snapshot(301)["status"], "PENDING")

    def test_wrong_remote_is_rejected(self):
        result = self.invoke(remote_url="https://github.com/attacker/unrelated.git")
        self.assertEqual(result["status"], "UNSAFE_REMOTE")
        self.assertEqual(self.store.snapshot(301)["status"], "PENDING")

    def test_closed_request_not_claimed(self):
        self.store.reconcile_open(set())
        self.assertEqual(self.invoke()["status"], "IDLE")
        self.assertEqual(self.store.snapshot(301)["status"], "CANCELLED")

    def test_fake_cli_commit_and_verified_remote_push(self):
        code = ('from pathlib import Path; import subprocess; '
                'Path("agent-output.txt").write_text("fake only"); '
                'subprocess.run(["git","add","agent-output.txt"],check=True); '
                'subprocess.run(["git","commit","-qm","fake agent commit"],check=True)')
        result = self.invoke((sys.executable, "-c", code))
        self.assertEqual(result["status"], "REPORTED_QA_PENDING")
        self.assertEqual(self.store.snapshot(301)["status"], "REPORTED")
        sha = self.git(["rev-parse", "HEAD"]).stdout.strip()
        remote_sha = self.git(["ls-remote", "origin", "refs/heads/work/qa-sim"]).stdout.split()[0]
        self.assertEqual(sha, remote_sha)
        self.assertIn(sha, result["proof"])
        self.assertNotIn("READY=1", result["proof"])


    def test_controller_push_does_not_execute_agent_controlled_pre_push_hook(self):
        """An agent may write .git/hooks/pre-push; never execute it with controller secrets."""
        hook = self.workdir / ".git" / "hooks" / "pre-push"
        marker_file = self.workdir / "hook-executed.txt"
        hook.write_text("#!/bin/sh\n" +
                        "printf unsafe > " + str(marker_file) + "\n" +
                        "exit 23\n")
        hook.chmod(0o755)
        code = ('from pathlib import Path; import subprocess; '
                'Path("agent-output.txt").write_text("fake only"); '
                'subprocess.run(["git","add","agent-output.txt"],check=True); '
                'subprocess.run(["git","commit","-qm","fake agent commit"],check=True)')
        result = self.invoke((sys.executable, "-c", code))
        self.assertEqual(result["status"], "REPORTED_QA_PENDING")
        self.assertFalse(marker_file.exists())
        self.assertEqual(self.store.snapshot(301)["status"], "REPORTED")


    def test_cancel_during_running_agent_terminates_cli_and_prevents_push(self):
        db_path = str(Path(self.temp.name) / "worker.db")
        def cancel():
            time.sleep(0.3)
            separate = DurableWorkStore(db_path)
            try:
                separate.reconcile_open(set())
            finally:
                separate.close()
        canceller = threading.Thread(target=cancel, daemon=True)
        canceller.start()
        started = time.monotonic()
        result = self.invoke((sys.executable, "-c", "import time; time.sleep(4)"),
                             timeout=8, heartbeat_interval=0.05)
        canceller.join(timeout=3)
        self.assertEqual(result["status"], "LEASE_LOST")
        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual(self.store.snapshot(301)["status"], "CANCELLED")
        self.assertFalse(self.git(["ls-remote", "origin",
                                   "refs/heads/work/qa-sim"]).stdout.strip())


    def test_existing_exact_draft_pr_is_reused(self):
        sha = "a" * 40
        existing = {"number": 500, "draft": True,
                    "head": {"ref": "work/qa-sim", "sha": sha},
                    "base": {"ref": "automation/event-driven-ready-gate-20261031"}}
        with patch("ai_agent_runner._github_json", return_value=[existing]) as api:
            number = ensure_draft_pr(
                repo="anigio2705-dev/hangeul-swipji", branch="work/qa-sim",
                base="automation/event-driven-ready-gate-20261031",
                sha=sha, token="test-only")
        self.assertEqual(number, 500)
        self.assertEqual(api.call_count, 1)

    def test_ambiguous_503_never_reposts(self):
        err = HTTPError("https://api.github.com", 503, "unavailable", {}, None)
        with patch("ai_agent_runner._github_json",
                   side_effect=[[], err, []]) as api:
            with self.assertRaises(DeliveryBlocked):
                ensure_draft_pr(
                    repo="anigio2705-dev/hangeul-swipji", branch="work/qa-sim",
                    base="automation/event-driven-ready-gate-20261031",
                    sha="a" * 40, token="test-only")
        self.assertEqual(api.call_count, 3)
        self.assertEqual(sum(call.args[0].endswith("/pulls") for call in
                             api.call_args_list), 1)

    def test_ambiguous_503_reconciles_created_pr_by_exact_sha(self):
        sha = "b" * 40
        existing = {"number": 501, "draft": True,
                    "head": {"ref": "work/qa-sim", "sha": sha},
                    "base": {"ref": "automation/event-driven-ready-gate-20261031"}}
        err = HTTPError("https://api.github.com", 503, "unavailable", {}, None)
        with patch("ai_agent_runner._github_json",
                   side_effect=[[], err, [existing]]) as api:
            number = ensure_draft_pr(
                repo="anigio2705-dev/hangeul-swipji", branch="work/qa-sim",
                base="automation/event-driven-ready-gate-20261031",
                sha=sha, token="test-only")
        self.assertEqual(number, 501)
        self.assertEqual(sum(call.args[0].endswith("/pulls") for call in
                             api.call_args_list), 1)

    def test_pr_handoff_rejects_main_base_without_network(self):
        with patch("ai_agent_runner._github_json") as api:
            with self.assertRaises(DeliveryBlocked):
                ensure_draft_pr(
                    repo="anigio2705-dev/hangeul-swipji", branch="work/qa-sim",
                    base="main", sha="a" * 40, token="test-only")
            api.assert_not_called()

    def test_push_failure_does_not_mark_reported(self):
        self.git(["remote", "remove", "origin"])
        code = ('from pathlib import Path; import subprocess; '
                'Path("agent-output.txt").write_text("fake only"); '
                'subprocess.run(["git","add","agent-output.txt"],check=True); '
                'subprocess.run(["git","commit","-qm","fake agent commit"],check=True)')
        result = self.invoke((sys.executable, "-c", code))
        self.assertEqual(result["status"], "PUSH_FAILED")
        self.assertNotEqual(self.store.snapshot(301)["status"], "REPORTED")


    def test_qa15_pushurl_override_cannot_push_to_rogue(self):
        rogue = Path(self.temp.name) / "rogue.git"
        subprocess.run(["git", "init", "--bare", "-q", str(rogue)], check=True)
        self.git(["remote", "set-url", "--push", "origin", str(rogue)])
        code = ('from pathlib import Path; import subprocess; '
                'Path("agent-output.txt").write_text("fake only"); '
                'subprocess.run(["git","add","agent-output.txt"],check=True); '
                'subprocess.run(["git","commit","-qm","fake agent commit"],check=True)')
        result = self.invoke((sys.executable, "-c", code))
        self.assertEqual(result["status"], "UNSAFE_PUSH_REMOTE")
        self.assertEqual(self.git(["ls-remote", str(rogue),
                                   "refs/heads/work/qa-sim"]).stdout.strip(), "")
        self.assertEqual(self.store.snapshot(301)["status"], "PENDING")

    def test_qa15_pushinstead_of_rewrite_is_blocked(self):
        rogue = Path(self.temp.name) / "rogue.git"
        self.git(["remote", "set-url", "origin",
                  "https://github.com/anigio2705-dev/hangeul-swipji.git"])
        self.git(["config", "url." + str(rogue) + ".pushInsteadOf",
                  "https://github.com/anigio2705-dev/hangeul-swipji.git"])
        allowed = {"https://github.com/anigio2705-dev/hangeul-swipji.git"}
        self.assertEqual(_origin_remote_status(str(self.workdir), allowed),
                         "UNSAFE_PUSH_REMOTE")

    def test_qa15_multiple_push_urls_are_blocked(self):
        safe = "https://github.com/anigio2705-dev/hangeul-swipji.git"
        self.git(["remote", "set-url", "origin", safe])
        self.git(["config", "--add", "remote.origin.pushurl", safe])
        self.git(["config", "--add", "remote.origin.pushurl", safe])
        self.assertEqual(_origin_remote_status(str(self.workdir), {safe}),
                         "UNSAFE_PUSH_REMOTE")

    def test_qa15_agent_changes_pushurl_after_initial_check(self):
        rogue = Path(self.temp.name) / "rogue.git"
        subprocess.run(["git", "init", "--bare", "-q", str(rogue)], check=True)
        code = ('from pathlib import Path; import subprocess; '
                'subprocess.run(["git","config","remote.origin.pushurl",'
                f'{str(rogue)!r}],check=True); '
                'Path("agent-output.txt").write_text("fake only"); '
                'subprocess.run(["git","add","agent-output.txt"],check=True); '
                'subprocess.run(["git","commit","-qm","fake agent commit"],check=True)')
        result = self.invoke((sys.executable, "-c", code))
        self.assertEqual(result["status"], "UNSAFE_PUSH_REMOTE")
        self.assertEqual(self.git(["ls-remote", str(rogue),
                                   "refs/heads/work/qa-sim"]).stdout.strip(), "")
        self.assertNotEqual(self.store.snapshot(301)["status"], "REPORTED")


    def test_qa15_lease_lost_at_push_handoff_blocks_remote_write(self):
        """Deterministic lease-loss race at push entry, not a real Codex call."""
        code = ('from pathlib import Path; import subprocess; '
                'Path("agent-output.txt").write_text("fake only"); '
                'subprocess.run(["git","add","agent-output.txt"],check=True); '
                'subprocess.run(["git","commit","-qm","fake agent commit"],check=True)')

        def expire_before_push(command, **kwargs):
            if command[:2] == ["git", "push"]:
                self.store.reconcile_open(set())
            return _run_with_lease(command, **kwargs)

        with patch("ai_agent_runner._run_with_lease",
                   side_effect=expire_before_push):
            result = self.invoke((sys.executable, "-c", code))
        self.assertEqual(result["status"], "LEASE_LOST")
        self.assertEqual(self.store.snapshot(301)["status"], "CANCELLED")
        self.assertEqual(self.git(["ls-remote", "origin",
                                   "refs/heads/work/qa-sim"]).stdout.strip(), "")


    def test_controller_rejects_agent_ssh_command_before_any_push(self):
        """Reproduce independent PR #172 without leaking even a fake token."""
        fake_ssh = Path(self.temp.name) / "qa-fake-ssh"
        exposure = Path(self.temp.name) / "qa-controller-token-exposed"
        fake_ssh.write_text("#!/bin/sh\\n" +
                            "printf '%s' \\"$GH_TOKEN\\" > " + repr(str(exposure)) +
                            "\\nexit 23\\n")
        fake_ssh.chmod(0o755)
        ssh_remote = "git@github.com:anigio2705-dev/hangeul-swipji.git"
        self.git(["remote", "set-url", "origin", ssh_remote])
        code = ('from pathlib import Path; import subprocess; '
                f'subprocess.run(["git","config","core.sshCommand",{str(fake_ssh)!r}],check=True); '
                'Path("agent-output.txt").write_text("fake only"); '
                'subprocess.run(["git","add","agent-output.txt"],check=True); '
                'subprocess.run(["git","commit","-qm","fake agent commit"],check=True)')
        with patch.dict(os.environ, {"GH_TOKEN": "qa15-fake-controller-sentinel"}):
            result = self.invoke((sys.executable, "-c", code),
                                 remote_url=ssh_remote)
        self.assertEqual(result["status"], "UNSAFE_GIT_CONFIG")
        self.assertFalse(exposure.exists())
        self.assertNotEqual(self.store.snapshot(301)["status"], "REPORTED")

    def test_controller_rejects_agent_credential_helper(self):
        code = ('from pathlib import Path; import subprocess; '
                'subprocess.run(["git","config","credential.helper",'
                '"!echo unsafe"],check=True); '
                'Path("agent-output.txt").write_text("fake only"); '
                'subprocess.run(["git","add","agent-output.txt"],check=True); '
                'subprocess.run(["git","commit","-qm","fake agent commit"],check=True)')
        result = self.invoke((sys.executable, "-c", code))
        self.assertEqual(result["status"], "UNSAFE_GIT_CONFIG")
        self.assertNotEqual(self.store.snapshot(301)["status"], "REPORTED")

    def test_controller_git_environment_excludes_all_controller_secrets(self):
        from ai_agent_runner import _controller_git_env
        with patch.dict(os.environ, {
            "GH_TOKEN": "fake-gh-token",
            "GITHUB_TOKEN": "fake-github-token",
            "OPENAI_API_KEY": "fake-codex-token",
            "GIT_SSH_COMMAND": "fake-command",
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.sshCommand",
            "GIT_CONFIG_VALUE_0": "fake-command",
        }):
            env = _controller_git_env()
        for key in ("GH_TOKEN", "GITHUB_TOKEN", "OPENAI_API_KEY",
                    "GIT_SSH_COMMAND", "GIT_CONFIG_COUNT",
                    "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0"):
            self.assertNotIn(key, env)


if __name__ == "__main__":
    unittest.main()
