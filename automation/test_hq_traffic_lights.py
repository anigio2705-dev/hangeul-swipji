"""Independent regression checks for the 160-contract dispatch readiness report."""
import tempfile
import unittest
from pathlib import Path
from hq_160_task_cycle import contracts
from hq_traffic_lights import readiness

def catalog():
    return contracts("\n".join(f"{i}. [ ] Item {i}" for i in range(1, 161)))

class ReadinessTests(unittest.TestCase):
    def test_unknown_and_unreviewed_tasks_cannot_be_reported_ready(self):
        c = catalog()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "feature.py").write_text("pass\n")
            (root / "test_feature.py").write_text("pass\n")
            reg = {"schema": 1, "items": {
                "22": {"owner": "13", "state": "BLOCKED", "source_paths": ["feature.py"], "test_paths": ["test_feature.py"]},
                "41": {"owner": "12", "state": "CANDIDATE", "source_paths": ["feature.py"], "test_paths": ["test_feature.py"]},
                "49": {"owner": "12", "state": "READY", "source_paths": ["feature.py"], "test_paths": ["test_feature.py"],
                       "independent_team15": "PENDING", "independent_ci_url": "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/123"}
            }}
            result = readiness(c, {}, reg, root)
            self.assertEqual(result["mapped_total"], 3)
            self.assertEqual(result["unmapped_total"], 157)
            self.assertEqual(result["dispatchable_total"], 0)
            self.assertEqual(result["blocked"], [22])
            self.assertEqual(result["candidates"], [41])
            self.assertEqual([x["task"] for x in result["invalid_ready"]], [49])

    def test_reviewed_ready_requires_real_paths_and_correct_owner(self):
        c = catalog()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name in ("feature.py", "test_feature.py"):
                (root / name).write_text("pass\n")
            record = {"owner": "12", "state": "READY", "source_paths": ["feature.py"],
                      "test_paths": ["test_feature.py"], "independent_team15": "PASS",
                      "independent_ci_url": "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/123"}
            reg = {"schema": 1, "items": {"49": record}}
            self.assertEqual(readiness(c, {}, reg, root)["dispatchable"], [{"task": 49, "owner": "12", "source_paths": ["feature.py"]}])
            record["owner"] = "13"
            self.assertEqual(readiness(c, {}, reg, root)["dispatchable_total"], 0)
            record["owner"] = "12"
            record["source_paths"] = ["../escape.py"]
            self.assertEqual(readiness(c, {}, reg, root)["dispatchable_total"], 0)

    def test_verified_not_counted_as_new_work_and_unknown_ids_fail(self):
        c = catalog()
        reg = {"schema": 1, "items": {"49": {"owner": "12", "state": "READY"}}}
        out = readiness(c, {"49": {"status": "code_verified"}}, reg)
        self.assertEqual(out["dispatchable_total"], 0)
        self.assertEqual(out["already_verified"], [49])
        with self.assertRaisesRegex(ValueError, "Unknown"):
            readiness(c, {}, {"schema": 1, "items": {"161": {}}})

    def test_parallel_ready_tasks_cannot_claim_the_same_source_file(self):
        c = catalog()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name in ("shared.py", "separate.py", "test_feature.py"):
                (root / name).write_text("pass\n")
            def record(path):
                return {"owner": "12", "state": "READY",
                        "source_paths": [path], "test_paths": ["test_feature.py"],
                        "independent_team15": "PASS",
                        "independent_ci_url": "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/123"}
            reg = {"schema": 1, "items": {
                "41": record("shared.py"), "49": record("shared.py")}}
            blocked = readiness(c, {}, reg, root)
            self.assertEqual(blocked["dispatchable_total"], 0)
            self.assertEqual({x["task"] for x in blocked["invalid_ready"]}, {41, 49})
            self.assertTrue(all("exclusive_file_collision" in x["reason"]
                                for x in blocked["invalid_ready"]))
            reg["items"]["49"] = record("separate.py")
            allowed = readiness(c, {}, reg, root)
            self.assertEqual(allowed["dispatchable_total"], 2)
            self.assertEqual(allowed["invalid_ready"], [])

if __name__ == "__main__":
    unittest.main()
