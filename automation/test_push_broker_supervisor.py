import os
import signal
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from push_broker_supervisor import PushRevoked, PushUncertain, supervise


class SupervisorTests(unittest.TestCase):
    def test_revoked_before_spawn(self):
        with self.assertRaises(PushRevoked):
            supervise(["nonexistent-broker-command"], lease_live=lambda: False)

    def test_success(self):
        result = supervise([sys.executable, "-c", "print('ok')"],
                           lease_live=lambda: True, timeout=2)
        self.assertEqual(result.stdout.strip(), "ok")

    def test_revocation_kills_process_group_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "orphan-wrote"
            state = {"live": True}
            def revoke():
                time.sleep(0.12)
                state["live"] = False
            t = threading.Thread(target=revoke)
            t.start()
            code = ('import subprocess,sys,time; '
                    'subprocess.Popen([sys.executable,"-c",'
                    '"import time,pathlib;time.sleep(0.5);pathlib.Path(sys.argv[1]).write_text(\\\'bad\\\')",'
                    'sys.argv[1]]);time.sleep(1)')
            with self.assertRaises((PushRevoked, PushUncertain)):
                supervise([sys.executable, "-c", code, str(marker)],
                          lease_live=lambda: state["live"], timeout=2)
            t.join()
            time.sleep(0.6)
            self.assertFalse(marker.exists())

    def test_zero_exit_with_background_child_is_uncertain(self):
        """A successful parent exit must not leave a delayed child writer."""
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "late-write"
            code = (
                "import subprocess,sys;"
                "subprocess.Popen([sys.executable,'-c',"
                "'import pathlib,sys,time;time.sleep(0.5);"
                "pathlib.Path(sys.argv[1]).write_text(\"bad\")',"
                "sys.argv[1]],stdin=subprocess.DEVNULL,"
                "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);"
                "print('parent-exited')"
            )
            with self.assertRaises(PushUncertain):
                supervise([sys.executable, "-c", code, str(marker)],
                          lease_live=lambda: True, timeout=2)
            time.sleep(0.65)
            self.assertFalse(marker.exists(), "orphan child wrote after parent exit")

    def test_detached_child_inheriting_pipes_cannot_stall_cleanup(self):
        """An escaped child must not hang the broker's cleanup indefinitely.

        This does NOT establish cgroup containment: a detached process can
        still outlive its original process group. Real push stays disabled.
        """
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = Path(tmp) / "escaped.pid"
            parent = (
                "import pathlib,subprocess,sys;"
                "p=subprocess.Popen([sys.executable,'-c',"
                "'import time;time.sleep(8)'],start_new_session=True);"
                "pathlib.Path(sys.argv[1]).write_text(str(p.pid));"
                "print('parent-exited')"
            )
            started = time.monotonic()
            try:
                with self.assertRaises(PushUncertain):
                    supervise([sys.executable, "-c", parent, str(pidfile)],
                              lease_live=lambda: True, timeout=0.2,
                              interval=0.03)
                self.assertLess(time.monotonic() - started, 4.5,
                                "escaped pipe holder stalled broker cleanup")
            finally:
                if pidfile.exists():
                    try:
                        os.kill(int(pidfile.read_text()), signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    def test_timeout_fail_closed(self):
        with self.assertRaises(PushUncertain):
            supervise([sys.executable, "-c", "import time;time.sleep(1)"],
                      lease_live=lambda: True, timeout=0.1)

    def test_invalid_command_or_timeout(self):
        for cmd, timeout in (([], 1), (["x"], 121)):
            with self.assertRaises(ValueError):
                supervise(cmd, lease_live=lambda: True, timeout=timeout)


if __name__ == "__main__":
    unittest.main()
