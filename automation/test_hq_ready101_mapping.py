"""Task #101: evidence-based runner compatibility, never an approval shortcut."""
import json
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "automation"))
from hq_160_task_cycle import load_catalog
from hq_traffic_lights import readiness


class Task101IntakeTests(unittest.TestCase):
    def test_canonical_owner_and_single_editable_python(self):
        catalog = load_catalog(ROOT / "automation/hq_backlog_160.md")
        registry = json.loads((ROOT / "automation/hq_semantic_contract_paths.json").read_text())
        item = registry["items"]["101"]
        self.assertEqual(catalog[101]["owner"], "14")
        self.assertEqual(item["owner"], "14")
        self.assertEqual(item["editable_path"], "phase3/team14_referral_store.py")
        self.assertIn(item["editable_path"], item["source_paths"])
        self.assertEqual(item["independent_team15"], "PENDING")
        self.assertEqual(item["state"], "CANDIDATE")
        # The actual Phase3 HTTP implementation is shared with other owners.
        # Map it for review, but never grant team14 an unlocked server edit.
        self.assertIn("phase3/server.py", item["source_paths"])
        self.assertIn("phase3/server.py", item["shared_integration_paths"])
        self.assertNotEqual("phase3/server.py", item["editable_path"])
        self.assertIn("phase3/test_team14_referral_http.py", item["test_paths"])
        self.assertIn("phase3/test_task101_four_pair_acceptance.py", item["test_paths"])
        self.assertTrue(all((ROOT / p).is_file() for p in item["source_paths"] + item["test_paths"]))
        self.assertTrue(all(p.endswith(".py") and Path(p).name.startswith("test_")
                            for p in item["test_paths"]))

    def test_cannot_dispatch_without_independent_review(self):
        catalog = load_catalog(ROOT / "automation/hq_backlog_160.md")
        registry = json.loads((ROOT / "automation/hq_semantic_contract_paths.json").read_text())
        ledger = json.loads((ROOT / "automation/task-evidence.json").read_text())
        result = readiness(catalog, ledger, registry, ROOT)
        self.assertEqual(result["dispatchable_total"], 0)
        self.assertIn(101, result["candidates"])


if __name__ == "__main__":
    unittest.main()
