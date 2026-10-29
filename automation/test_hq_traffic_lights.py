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

    def test_six_team_candidate_supply_is_diagnostic_not_dispatch(self):
        c = catalog()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name in ("one.py", "two.py", "test_one.py"):
                (root / name).write_text("pass\\n")
            def candidate(owner, sources, tests, review="PENDING"):
                return {"owner": owner, "state": "CANDIDATE",
                        "source_paths": sources, "test_paths": tests,
                        "independent_team15": review, "unmet": ["browser E2E"]}
            reg = {"schema": 1, "items": {
                "11": candidate("11", ["one.py"], ["test_one.py"]),
                "41": candidate("12", ["one.py", "two.py"], []),
                "9": candidate("15", ["../outside.py"], ["test_one.py"]),
                "143": candidate("16", ["one.py"], ["test_one.py"], "PASS"),
                "22": {"owner": "13", "state": "BLOCKED"},
            }}
            out = readiness(c, {}, reg, root)
            self.assertEqual(out["dispatchable_total"], 0)
            self.assertEqual(set(out["candidate_supply"]), {"11", "12", "13", "14", "15", "16"})
            self.assertEqual(out["candidate_supply_next"]["11"], 11)
            self.assertEqual(out["candidate_supply_next"]["12"], 41)
            self.assertIsNone(out["candidate_supply_next"]["13"])
            self.assertEqual(out["candidate_supply_next"]["16"], 143)
            self.assertIn("team15_independent_review_pending",
                          out["candidate_supply"]["11"][0]["blockers"])
            self.assertIn("explicit_single_editable_path_required",
                          out["candidate_supply"]["12"][0]["blockers"])
            self.assertIn("missing_or_invalid_test_path",
                          out["candidate_supply"]["12"][0]["blockers"])
            self.assertIn("missing_or_invalid_source_path",
                          out["candidate_supply"]["15"][0]["blockers"])
            self.assertEqual(out["candidate_supply"]["16"][0]["blockers"], [])
            self.assertEqual(out["candidate_supply"]["16"][0]["state"], "CANDIDATE")
            self.assertEqual(out["blocked"], [22])

    def test_candidate_supply_does_not_reopen_code_verified_work(self):
        c = catalog()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "one.py").write_text("pass\\n")
            (root / "test_one.py").write_text("pass\\n")
            reg = {"schema": 1, "items": {
                "49": {"owner": "12", "state": "CANDIDATE",
                       "source_paths": ["one.py"], "test_paths": ["test_one.py"]}
            }}
            out = readiness(c, {"49": {"status": "code_verified"}}, reg, root)
            self.assertEqual(out["already_verified"], [49])
            self.assertEqual(out["candidate_supply"]["12"], [])
            self.assertIsNone(out["candidate_supply_next"]["12"])

    def test_multi_source_ready_requires_reviewed_single_editable_path(self):
        from hq_160_task_cycle import next_assignment
        c = catalog()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name in ("target.py", "context.py", "test_target.py"):
                (root / name).write_text("pass\\n")
            record = {
                "owner": "12", "state": "READY",
                "source_paths": ["target.py", "context.py"],
                "test_paths": ["test_target.py"], "independent_team15": "PASS",
                "independent_ci_url": "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/123",
            }
            reg = {"schema": 1, "items": {"41": record}}
            without = readiness(c, {}, reg, root)
            self.assertEqual(without["dispatchable_total"], 0)
            self.assertIn("single_editable_path", without["invalid_ready"][0]["reason"])
            self.assertIsNone(next_assignment("12", c, {}, registry=reg, root=root))
            record["editable_path"] = "../outside.py"
            self.assertEqual(readiness(c, {}, reg, root)["dispatchable_total"], 0)
            record["editable_path"] = "test_target.py"
            self.assertEqual(readiness(c, {}, reg, root)["dispatchable_total"], 0)
            record["editable_path"] = "target.py"
            allowed = readiness(c, {}, reg, root)
            self.assertEqual(allowed["dispatchable_total"], 1)
            self.assertEqual(allowed["dispatchable"][0]["editable_path"], "target.py")
            assigned = next_assignment("12", c, {}, registry=reg, root=root)
            self.assertEqual(assigned["task_number"], 41)
            self.assertEqual(assigned["path"], "target.py")
            self.assertEqual(assigned["independent_test_paths"], ["test_target.py"])
            # A code-verified item is never re-opened by the same READY record.
            self.assertIsNone(next_assignment("12", c,
                              {"41": {"status": "code_verified"}}, registry=reg, root=root))

    def test_shared_readonly_context_does_not_block_distinct_editable_targets(self):
        """Two teams may read the same context, but cannot edit the same file."""
        c = catalog()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name in ("shared_context.py", "edit_41.py", "edit_49.py", "test_41.py", "test_49.py"):
                (root / name).write_text("pass\n")
            def record(number):
                target = f"edit_{number}.py"
                return {"owner": "12", "state": "READY",
                        "source_paths": ["shared_context.py", target],
                        "editable_path": target, "test_paths": [f"test_{number}.py"],
                        "independent_team15": "PASS",
                        "independent_ci_url":
                            "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/123"}
            reg = {"schema": 1, "items": {"41": record(41), "49": record(49)}}
            result = readiness(c, {}, reg, root)
            self.assertEqual(result["dispatchable_total"], 2)
            self.assertEqual(result["invalid_ready"], [])
            reg["items"]["49"]["editable_path"] = "edit_41.py"
            reg["items"]["49"]["source_paths"].append("edit_41.py")
            collision = readiness(c, {}, reg, root)
            self.assertEqual(collision["dispatchable_total"], 0)
            self.assertEqual({x["task"] for x in collision["invalid_ready"]}, {41, 49})

if __name__ == "__main__":
    unittest.main()
