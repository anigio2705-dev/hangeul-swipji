import os
import tempfile
import unittest
from pathlib import Path
from push_broker_os_guard import IsolationDenied, verify_broker_isolation


class BrokerOSGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'broker'
        self.root.mkdir(mode=0o700)
        self.db = self.root / 'leases.sqlite'
        self.db.write_bytes(b'not a real database: permissions only')
        self.db.chmod(0o600)
        self.credential = self.root / 'gh_token'
        self.credential.write_text('fake-only')
        self.credential.chmod(0o600)
        self.uid = os.stat(self.root).st_uid
        # Actual broker must be a separate non-root OS identity.
        if self.uid == 0:
            self.skipTest('run as unprivileged user for ownership tests')

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, **kwargs):
        return verify_broker_isolation(str(self.db), str(self.credential),
                                       agent_uid=self.uid + 1,
                                       trusted_root=str(self.root),
                                       **kwargs)

    def test_private_separate_uid(self):
        self.assertTrue(self.check())

    def test_same_uid_denied(self):
        with self.assertRaises(IsolationDenied):
            verify_broker_isolation(str(self.db), str(self.credential),
                                    agent_uid=self.uid, trusted_root=str(self.root))

    def test_group_writable_root_denied(self):
        self.root.chmod(0o770)
        with self.assertRaises(IsolationDenied):
            self.check()

    def test_world_readable_db_denied(self):
        self.db.chmod(0o644)
        with self.assertRaises(IsolationDenied):
            self.check()

    def test_writable_wal_denied(self):
        wal = Path(str(self.db) + '-wal')
        wal.write_text('fake')
        wal.chmod(0o666)
        with self.assertRaises(IsolationDenied):
            self.check()

    def test_credential_exposure_denied(self):
        self.credential.chmod(0o640)
        with self.assertRaises(IsolationDenied):
            self.check()

    def test_symlink_db_denied(self):
        other = self.root / 'other'
        other.write_text('fake')
        other.chmod(0o600)
        self.db.unlink()
        self.db.symlink_to(other)
        with self.assertRaises(IsolationDenied):
            self.check()

    def test_agent_path_outside_root_denied(self):
        with self.assertRaises(IsolationDenied):
            verify_broker_isolation(str(self.credential), str(self.credential),
                                    agent_uid=self.uid + 1,
                                    trusted_root=str(self.root / 'different'))


    def test_agent_writable_broker_ancestor_denied(self):
        shared = Path(self.tmp.name) / 'shared'
        shared.mkdir()
        shared.chmod(0o777)
        root = shared / 'broker'
        root.mkdir(mode=0o700)
        db = root / 'leases.sqlite'
        db.write_bytes(b'fake')
        db.chmod(0o600)
        token = root / 'fake_token'
        token.write_text('fake')
        token.chmod(0o600)
        with self.assertRaises(IsolationDenied):
            verify_broker_isolation(db, token, agent_uid=self.uid + 1,
                                    trusted_root=root)

    def test_agent_writable_credential_ancestor_denied(self):
        shared = Path(self.tmp.name) / 'shared_credential'
        shared.mkdir()
        shared.chmod(0o777)
        token = shared / 'fake_token'
        token.write_text('fake')
        token.chmod(0o600)
        with self.assertRaises(IsolationDenied):
            verify_broker_isolation(self.db, token, agent_uid=self.uid + 1,
                                    trusted_root=self.root)

    def test_nonroot_sticky_credential_parent_denied(self):
        shared = Path(self.tmp.name) / 'sticky_credential'
        shared.mkdir()
        shared.chmod(0o1777)
        token = shared / 'fake_token'
        token.write_text('fake')
        token.chmod(0o600)
        with self.assertRaises(IsolationDenied):
            verify_broker_isolation(self.db, token, agent_uid=self.uid + 1,
                                    trusted_root=self.root)


if __name__ == '__main__':
    unittest.main()
