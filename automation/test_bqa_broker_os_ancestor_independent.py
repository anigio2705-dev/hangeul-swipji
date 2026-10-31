"""B/15 independent negative tests: path ownership preflight is not enough.

Exact C product-security reQA SHA 7a3a77602756f53ce2d554577d9bb72ffc4c020f.
Prior SHA 541119ab0eb13ed8d38df6318e58f48e7808ea21 was QA_FAIL.
No real credentials/push.
"""
import os
import tempfile
import unittest
from pathlib import Path
from push_broker_os_guard import IsolationDenied, verify_broker_isolation


class BQABrokerAncestorIsolationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.uid = os.geteuid()
        if self.uid == 0:
            self.skipTest("requires non-root POSIX runner; never count as PASS")
        self.base.chmod(0o755)
        self.agent_uid = self.uid + 1

    def _files(self, root):
        root.mkdir(mode=0o700)
        db = root / "leases.sqlite"
        db.write_bytes(b"isolated test only")
        db.chmod(0o600)
        token = root / "fake_credential"
        token.write_text("dummy, not a real credential")
        token.chmod(0o600)
        return db, token

    def test_agent_writable_ancestor_of_broker_root_must_fail_closed(self):
        # An agent-writable, non-sticky ancestor can replace the trusted
        # directory after preflight, despite its own 0700 mode.
        shared = self.base / "shared"
        shared.mkdir(mode=0o777)
        shared.chmod(0o777)
        root = shared / "broker"
        db, token = self._files(root)
        with self.assertRaises(IsolationDenied, msg="writable ancestor accepted"):
            verify_broker_isolation(db, token, agent_uid=self.agent_uid,
                                    trusted_root=root)

    def test_agent_writable_credential_parent_must_fail_closed(self):
        # The credential itself is 0600, but its containing directory can
        # be replaced by a different OS principal between check and use.
        root = self.base / "broker"
        db, _ = self._files(root)
        shared = self.base / "agent_writable_credentials"
        shared.mkdir(mode=0o777)
        shared.chmod(0o777)
        token = shared / "fake_credential"
        token.write_text("dummy")
        token.chmod(0o600)
        with self.assertRaises(IsolationDenied, msg="unsafe credential parent accepted"):
            verify_broker_isolation(db, token, agent_uid=self.agent_uid,
                                    trusted_root=root)


if __name__ == "__main__":
    unittest.main()
