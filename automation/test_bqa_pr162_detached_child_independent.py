"""Independent B/15 PR #162 corrected exact-SHA reQA: detached-child cleanup.
Only fake Python processes, local temporary files; no GitHub push or credentials.
This is NOT a production cgroup test or a live-host authorization.
"""
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from ai_agent_runner import _run_with_lease


class _Heartbeat:
    def __init__(self, cancel_after=None):
        self.calls = 0
        self.cancel_after = cancel_after

    def heartbeat(self, issue, owner, lease_seconds):
        self.calls += 1
        return self.cancel_after is None or self.calls < self.cancel_after


def _kill_pid_file(pidfile):
    if pidfile.exists():
        try:
            os.kill(int(pidfile.read_text()), signal.SIGKILL)
        except ProcessLookupError:
            pass


class IndependentDetachedChildTests(unittest.TestCase):
    def test_01_detached_pipe_holder_cannot_hang_bounded_reap(self):
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = Path(tmp) / "child.pid"
            parent = (
                "import pathlib,subprocess,sys;"
                "p=subprocess.Popen([sys.executable,'-c',"
                "'import time;time.sleep(5)'],start_new_session=True);"
                "pathlib.Path(sys.argv[1]).write_text(str(p.pid));"
                "print('parent-exit')"
            )
            started = time.monotonic()
            try:
                with self.assertRaises(subprocess.TimeoutExpired):
                    _run_with_lease(
                        [sys.executable, "-c", parent, str(pidfile)],
                        cwd=tmp, store=_Heartbeat(), issue=162, owner="qa-only",
                        timeout=0.2, heartbeat_interval=0.03)
                self.assertLess(time.monotonic() - started, 3,
                                "worker stuck waiting on escaped pipe holder")
            finally:
                _kill_pid_file(pidfile)

    def test_02_cancelled_lease_must_not_leave_detached_writer(self):
        """Red-team requirement: lease cancellation must fence every child.

        Prior exact SHA failed because a child using start_new_session=True
        escaped the direct parent's process group. This test rechecks the
        corrected SHA; passing is NOT cgroup/UID/host security approval.
        """
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = Path(tmp) / "child.pid"
            marker = Path(tmp) / "post-cancel-write"
            child = (
                "import pathlib,sys,time;"
                "time.sleep(0.55);"
                "pathlib.Path(sys.argv[1]).write_text('escaped')"
            )
            parent = (
                "import pathlib,subprocess,sys,time;"
                "p=subprocess.Popen([sys.executable,'-c',sys.argv[3],sys.argv[2]],"
                "start_new_session=True);"
                "pathlib.Path(sys.argv[1]).write_text(str(p.pid));"
                "time.sleep(3)"
            )
            try:
                result = _run_with_lease(
                    [sys.executable, "-c", parent, str(pidfile),
                     str(marker), child],
                    cwd=tmp, store=_Heartbeat(cancel_after=2),
                    issue=162, owner="qa-only", timeout=2,
                    heartbeat_interval=0.12)
                self.assertIsNone(result, "lease loss must abort work")
                time.sleep(0.75)
                self.assertFalse(marker.exists(),
                                 "detached child wrote AFTER lease cancellation")
            finally:
                _kill_pid_file(pidfile)


if __name__ == "__main__":
    unittest.main()
