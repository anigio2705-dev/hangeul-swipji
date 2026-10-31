import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from push_broker_cgroup_guard import CgroupDenied, verify_cgroup_placement


class CgroupPlacementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.proc = self.root / "proc"
        self.cg = self.root / "sys" / "fs" / "cgroup"
        self.broker = "/system.slice/hangeul-push-broker.service"
        self.agent = "/system.slice/hangeul-ai-worker.service"
        (self.cg / "system.slice" / "hangeul-push-broker.service").mkdir(parents=True)
        (self.cg / "system.slice" / "hangeul-ai-worker.service").mkdir(parents=True)
        (self.cg / "cgroup.controllers").write_text("cpu memory")
        (self.cg / self.broker.lstrip("/") / "cgroup.kill").write_text("")
        (self.cg / self.broker.lstrip("/") / "cgroup.procs").write_text("111\\n")
        self.set_member(111, self.broker)
        self.set_member(222, self.agent)

    def tearDown(self):
        self.temp.cleanup()

    def set_member(self, pid, path):
        p = self.proc / str(pid)
        p.mkdir(parents=True, exist_ok=True)
        (p / "cgroup").write_text("0::" + path + "\\n")

    def verify(self):
        return verify_cgroup_placement(agent_pid=222, broker_pid=111,
                                       proc_root=str(self.proc), cgroup_root=str(self.cg))

    def test_separate_units_and_kernel_kill(self):
        self.assertEqual(self.verify()["broker_cgroup"], self.broker)

    def test_same_cgroup_denied(self):
        self.set_member(222, self.broker)
        with self.assertRaises(CgroupDenied):
            self.verify()

    def test_nested_agent_cgroup_denied(self):
        self.set_member(222, self.broker + "/child")
        with self.assertRaises(CgroupDenied):
            self.verify()

    def test_missing_kernel_kill_denied(self):
        (self.cg / self.broker.lstrip("/") / "cgroup.kill").unlink()
        with self.assertRaises(CgroupDenied):
            self.verify()

    def test_broker_not_in_procs_denied(self):
        (self.cg / self.broker.lstrip("/") / "cgroup.procs").write_text("333\\n")
        with self.assertRaises(CgroupDenied):
            self.verify()

    def test_wrong_broker_unit_denied(self):
        self.set_member(111, self.agent)
        with self.assertRaises(CgroupDenied):
            self.verify()

    def test_cgroup_v1_denied(self):
        (self.cg / "cgroup.controllers").unlink()
        with self.assertRaises(CgroupDenied):
            self.verify()

    def test_untrusted_path_denied(self):
        self.set_member(222, "/system.slice/../hangeul-ai-worker.service")
        with self.assertRaises(CgroupDenied):
            self.verify()

    def test_unavailable_proc_denied(self):
        (self.proc / "222" / "cgroup").unlink()
        with self.assertRaises(CgroupDenied):
            self.verify()

    def test_invalid_agent_pid_denied(self):
        with self.assertRaises(CgroupDenied):
            verify_cgroup_placement(agent_pid=True, broker_pid=111,
                                    proc_root=str(self.proc), cgroup_root=str(self.cg))


if __name__ == "__main__":
    unittest.main()
