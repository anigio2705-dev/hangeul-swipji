"""Local regression of request replay and restart-safe QA_PENDING storage."""
import importlib.util
import tempfile
import unittest
import sqlite3
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

path=Path(__file__).with_name("qa_pending_store.py")
spec=importlib.util.spec_from_file_location("qa_pending_store",path)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
PendingStore=module.PendingStore
SHA="8f4eba4e3044e75e5a137b2b1ba82e791a4b148b"

class PendingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/"pending.sqlite"
        self.store=PendingStore(self.path)
    def tearDown(self):
        self.tmp.cleanup()
    def test_issue_and_restart(self):
        self.store.issue("AB-LAB-140-001",140,266,SHA)
        self.assertTrue(PendingStore(self.path).require_pending("AB-LAB-140-001",140,266,SHA))
    def test_request_id_replay(self):
        self.store.issue("AB-LAB-140-001",140,266,SHA)
        with self.assertRaisesRegex(ValueError,"REQUEST_ID_REPLAY"):
            self.store.issue("AB-LAB-140-001",140,267,SHA)
    def test_duplicate_product_new_request_id(self):
        self.store.issue("AB-LAB-140-001",140,266,SHA)
        with self.assertRaisesRegex(ValueError,"DUPLICATE_PRODUCT_REQUEST"):
            self.store.issue("AB-LAB-140-002",140,266,SHA)
    def test_forged_pending(self):
        with self.assertRaisesRegex(ValueError,"UNAUTHORIZED_OR_REPLAYED_REQUEST"):
            self.store.require_pending("AB-LAB-140-001",140,266,SHA)
    def test_consume_once_after_restart(self):
        self.store.issue("AB-LAB-140-001",140,266,SHA)
        self.assertTrue(self.store.consume_pending("AB-LAB-140-001",140,266,SHA))
        with self.assertRaisesRegex(ValueError,"UNAUTHORIZED_OR_REPLAYED_REQUEST"):
            PendingStore(self.path).consume_pending("AB-LAB-140-001",140,266,SHA)
    def test_twelve_concurrent_issuers_one_winner(self):
        def attempt(i):
            try:
                PendingStore(self.path).issue(f"AB-LAB-140-{i:03d}",140,266,SHA)
                return "issued"
            except ValueError:
                return "rejected"
        with ThreadPoolExecutor(max_workers=12) as pool:
            results=list(pool.map(attempt,range(12)))
        self.assertEqual(results.count("issued"),1)
        self.assertEqual(results.count("rejected"),11)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM pending").fetchone()[0],1)
            self.assertEqual(db.execute("SELECT count(*) FROM request_attempts").fetchone()[0],12)
    def test_rejection_audit_persists_new_connection(self):
        self.store.issue("AB-LAB-140-001",140,266,SHA)
        with self.assertRaisesRegex(ValueError,"REQUEST_ID_REPLAY"):
            self.store.issue("AB-LAB-140-001",140,267,SHA)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute(
                "SELECT result FROM request_attempts ORDER BY rowid DESC LIMIT 1"
            ).fetchone()[0],"REPLAY_REJECTED")
    def test_permissions_rejected(self):
        os.chmod(self.path,0o666)
        with self.assertRaisesRegex(ValueError,"SQLITE_UNSAFE_PERMISSIONS"):
            self.store.require_pending("AB-LAB-140-001",140,266,SHA)
    def test_file_replacement_rejected(self):
        self.path.unlink()
        self.path.touch(mode=0o600)
        with self.assertRaisesRegex(ValueError,"SQLITE_FILE_REPLACED"):
            self.store.require_pending("AB-LAB-140-001",140,266,SHA)
    def test_binding_mismatch(self):
        self.store.issue("AB-LAB-140-001",140,266,SHA)
        with self.assertRaisesRegex(ValueError,"UNAUTHORIZED_OR_REPLAYED_REQUEST"):
            self.store.require_pending("AB-LAB-140-001",140,267,SHA)

if __name__=="__main__":
    unittest.main()
