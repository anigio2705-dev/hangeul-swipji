"""Local regression of request replay and restart-safe QA_PENDING storage."""
import importlib.util
import tempfile
import unittest
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
    def test_binding_mismatch(self):
        self.store.issue("AB-LAB-140-001",140,266,SHA)
        with self.assertRaisesRegex(ValueError,"UNAUTHORIZED_OR_REPLAYED_REQUEST"):
            self.store.require_pending("AB-LAB-140-001",140,267,SHA)

if __name__=="__main__":
    unittest.main()
