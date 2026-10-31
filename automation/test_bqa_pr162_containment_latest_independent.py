"""B/15 independent C #162 latest-SHA containment regressions.

Only temporary local Python subprocesses, never real Codex, credentials or push.
Scoped security QA only; does NOT establish cgroup/UID or 24-hour host safety.
"""
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

from ai_agent_runner import _run_with_lease, AgentContainmentError


class Lease:
    def __init__(self, cancel_at=None):
        self.n = 0
        self.cancel_at = cancel_at

    def heartbeat(self, issue, owner, lease_seconds):
        self.n += 1
        return self.cancel_at is None or self.n < self.cancel_at


def cleanup(pidfile):
    if pidfile.exists():
        try:
            os.kill(int(pidfile.read_text()), signal.SIGKILL)
        except ProcessLookupError:
            pass


class BQA162Containment(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "linux" and Path("/proc").is_dir(),
                         "Linux procfs required")
    def test_01_zero_exit_with_live_detached_writer_must_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = Path(tmp) / "child.pid"
            marker = Path(tmp) / "escaped_write"
            child = ("import pathlib,sys,time;"
                     "time.sleep(1.1);"
                     "pathlib.Path(sys.argv[1]).write_text('escaped')")
            parent = ("import pathlib,subprocess,sys,time;"
                      "p=subprocess.Popen([sys.executable,'-c',sys.argv[3],sys.argv[2]],"
                      "start_new_session=True,stdout=subprocess.DEVNULL,"
                      "stderr=subprocess.DEVNULL);"
                      "pathlib.Path(sys.argv[1]).write_text(str(p.pid));"
                      "time.sleep(0.25);"
                      "print('success')")
            try:
                with self.assertRaises(AgentContainmentError):
                    _run_with_lease(
                        [sys.executable, "-c", parent, str(pidfile), str(marker), child],
                        cwd=tmp, store=Lease(), issue=162, owner="bqa",
                        timeout=2, heartbeat_interval=0.03)
                time.sleep(1.2)
                self.assertFalse(marker.exists(), "detached writer escaped successful exit")
            finally:
                cleanup(pidfile)

    @unittest.skipUnless(sys.platform == "linux" and Path("/proc").is_dir(),
                         "Linux procfs required")
    def test_02_child_that_exits_before_parent_is_not_false_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = ("import subprocess,sys;"
                    "subprocess.run([sys.executable,'-c','print(123)'],"
                    "start_new_session=True,check=True);"
                    "print('parent-finished')")
            result = _run_with_lease(
                [sys.executable, "-c", code], cwd=tmp,
                store=Lease(), issue=162, owner="bqa", timeout=3,
                heartbeat_interval=0.03)
            self.assertEqual(result.returncode, 0)
            self.assertIn("parent-finished", result.stdout)

    @unittest.skipUnless(sys.platform == "linux" and Path("/proc").is_dir(),
                         "Linux procfs required")
    def test_03_lease_revocation_kills_detached_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = Path(tmp) / "child.pid"
            marker = Path(tmp) / "post_cancel"
            child = ("import pathlib,sys,time;"
                     "time.sleep(0.6);"
                     "pathlib.Path(sys.argv[1]).write_text('escaped')")
            parent = ("import pathlib,subprocess,sys,time;"
                      "p=subprocess.Popen([sys.executable,'-c',sys.argv[3],sys.argv[2]],"
                      "start_new_session=True);"
                      "pathlib.Path(sys.argv[1]).write_text(str(p.pid));"
                      "time.sleep(3)")
            try:
                result = _run_with_lease(
                    [sys.executable, "-c", parent, str(pidfile), str(marker), child],
                    cwd=tmp, store=Lease(cancel_at=3), issue=162, owner="bqa",
                    timeout=2, heartbeat_interval=0.12)
                self.assertIsNone(result)
                time.sleep(0.8)
                self.assertFalse(marker.exists())
            finally:
                cleanup(pidfile)

    @unittest.skipUnless(sys.platform == "linux" and Path("/proc").is_dir(),
                         "Linux procfs required")
    def test_04_detached_pipe_holder_never_causes_unbounded_wait(self):
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = Path(tmp) / "child.pid"
            parent = ("import pathlib,subprocess,sys;"
                      "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(4)'],"
                      "start_new_session=True);"
                      "pathlib.Path(sys.argv[1]).write_text(str(p.pid));"
                      "print('parent-done')")
            started = time.monotonic()
            try:
                with self.assertRaises(subprocess.TimeoutExpired):
                    _run_with_lease(
                        [sys.executable, "-c", parent, str(pidfile)],
                        cwd=tmp, store=Lease(), issue=162, owner="bqa",
                        timeout=0.2, heartbeat_interval=0.03)
                self.assertLess(time.monotonic()-started, 3)
            finally:
                cleanup(pidfile)


if __name__ == "__main__":
    unittest.main()
