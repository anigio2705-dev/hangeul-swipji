import unittest
from unittest.mock import patch
from pathlib import Path

from hq_160_task_cycle import (
    CURATED_TARGETS, contracts, make_report, next_assignment, verify_submission,
)

def sample():
    return "\n".join(f"{n}. [ ] Criterion for item {n}" for n in range(1, 161))

class HQ160TaskCycleTests(unittest.TestCase):
    def test_real_master_160_criteria_are_mapped_to_6_teams(self):
        source = Path(__file__).parent / "hq_backlog_160.md"
        tasks = contracts(source.read_text(encoding="utf-8"))
        self.assertEqual(list(tasks), list(range(1, 161)))
        self.assertEqual({x["owner"] for x in tasks.values()}, set(CURATED_TARGETS))
        self.assertTrue(all(x["criterion"] and x["evidence_required"] for x in tasks.values()))
        self.assertTrue(all(x["owner"] not in x["support"] for x in tasks.values()))
        self.assertTrue(tasks[154]["external_gate"])
        self.assertTrue(tasks[154]["approval_gate"])
        self.assertIn(151, tasks[154]["dependencies"])
        self.assertEqual(tasks[9]["owner"], "15")

    def test_reject_duplicate_or_missing_item(self):
        with self.assertRaisesRegex(ValueError, "160"):
            contracts(sample() + "\n160. [ ] duplicate")
        with self.assertRaisesRegex(ValueError, "160"):
            contracts(sample().replace("4. [ ]", "5. [ ]"))

    def test_empty_unreviewed_queue_does_not_dispatch_curated_targets(self):
        report = make_report(sample())
        self.assertEqual(report["final_complete"], 0)
        self.assertEqual(len(report["assignments"]), 6)
        self.assertTrue(all(assignment is None for assignment in report["assignments"].values()),
                        "No independently READY item exists; old curated IDs are not authorization")

    @patch("hq_160_task_cycle._semantic_dispatch_gate", return_value=True)
    def test_code_verified_skips_reimplementation_and_assigns_next(self, _legacy_gate):
        catalog = contracts(sample())
        task = next_assignment("12", catalog, {"41": {"status": "code_verified"}})
        self.assertEqual(task["task_number"], 52)
        self.assertEqual(next_assignment("12", catalog, {
            "41": {"status": "code_verified"}, "52": {"status": "code_verified"},
        })["task_number"], 49)
        self.assertIsNone(next_assignment("12", catalog, {
            "41": {"status": "code_verified"}, "52": {"status": "code_verified"},
            "49": {"status": "code_verified"},
        }))

    @patch("hq_160_task_cycle._semantic_dispatch_gate", return_value=True)
    def test_pending_independent_ci_is_not_assigned_again(self, _legacy_gate):
        catalog = contracts(sample())
        pending = {"41": {"status": "in_progress", "independent_review": "pass"}}
        self.assertEqual(next_assignment("12", catalog, pending)["task_number"], 52)
        pending["52"] = {"status": "code_verified"}
        self.assertEqual(next_assignment("12", catalog, pending)["task_number"], 49)

    def test_unverified_snapshot_cannot_dispatch_blocked_semantic_contract(self):
        catalog = contracts(sample())
        self.assertIsNone(next_assignment("13", catalog, evidence={}),
                          "A missing ledger entry must not reopen blocked #22")
        from hq_160_task_cycle import _semantic_dispatch_gate
        next11 = next_assignment("11", catalog, evidence={})
        if _semantic_dispatch_gate(56, "scripts/find-human-audio-sources.py"):
            self.assertEqual(56, next11["task_number"])
        else:
            self.assertIsNone(next11, "Both #51 and #56 candidates must be quarantined")

    def test_wrong_scope_47_is_not_assigned_to_team13(self):
        catalog = contracts(sample())
        ledger = {"22": {"status": "blocked"},
                  "47": {"status": "in_progress", "independent_review": "pass",
                         "task_specific_verified": False}}
        self.assertNotIn((47, "phase3/learning.py"), CURATED_TARGETS["13"])
        self.assertIsNone(next_assignment("13", catalog, ledger))
        self.assertEqual(catalog[47]["owner"], "12")

    @patch("hq_160_task_cycle._semantic_dispatch_gate", return_value=True)
    def test_failure_feedback_is_specific_and_retry_is_bounded(self, _legacy_gate):
        catalog = contracts(sample())
        failure = {"8": {"attempts": 1, "repair_instruction": "Fix failed assertion 42"}}
        task = next_assignment("15", catalog, failures=failure)
        self.assertEqual(task["task_number"], 8)
        self.assertEqual(task["mode"], "repair")
        self.assertEqual(task["attempt"], 2)
        self.assertIn("assertion 42", task["repair_instruction"])
        next_task = next_assignment("15", catalog, failures={"8": {"attempts": 2}, "151": {"attempts": 2}})
        # This test mocks the old gate to isolate bounded retry logic; both candidates exhausted.
        self.assertIsNone(next_task)

    @patch("hq_160_task_cycle._semantic_dispatch_gate", return_value=True)
    def test_independent_verification_not_developer_self_report(self, _legacy_gate):
        assignment = next_assignment("15", contracts(sample()))
        sha = "a" * 40
        submission = {"commit": sha, "developer_says_passed": True}
        trusted = {
            "branch_head": sha, "changed_files": [assignment["path"]],
            "independent_test": "failure", "test_error": "assertion 42",
            "ci_conclusion": "success",
            "ci_url": "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/123", "independent_ci_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        }
        failure = verify_submission(assignment, submission, trusted)
        self.assertEqual(failure["verdict"], "RETRY")
        self.assertIn("assertion 42", failure["repair_instruction"])
        trusted["independent_test"] = "success"
        trusted["ci_conclusion"] = "failure"
        self.assertEqual(verify_submission(assignment, submission, trusted)["verdict"], "RETRY")
        trusted["ci_conclusion"] = "success"
        trusted["ci_head_sha"] = "b" * 40
        mismatch = verify_submission(assignment, submission, trusted)
        self.assertEqual(mismatch["verdict"], "RETRY")
        self.assertIn("exact commit", mismatch["repair_instruction"])
        trusted["ci_head_sha"] = sha
        passed = verify_submission(assignment, submission, trusted)
        self.assertEqual(passed["verdict"], "CODE_VERIFIED")
        self.assertNotEqual(passed["verdict"], "COMPLETE")
        trusted["changed_files"] = ["other.py"]
        self.assertEqual(verify_submission(assignment, submission, trusted)["verdict"], "RETRY")

    def test_final_complete_requires_master_check(self):
        self.assertEqual(make_report(sample(), {"9": {"status": "complete"}})["final_complete"], 0)
        checked = sample().replace("9. [ ]", "9. [x]")
        self.assertEqual(make_report(checked, {"9": {"status": "complete"}})["final_complete"], 0)
        proof = {"status": "complete", "commit": "a" * 40,
                 "ci_conclusion": "success", "independent_review": "pass",
                 "ci_url": "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/123", "independent_ci_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
        self.assertEqual(make_report(checked, {"9": proof})["final_complete"], 1)

    def test_semantic_contract_paths_and_wrong_scope_regressions(self):
        import json
        root = Path(__file__).resolve().parents[1]
        mapping = json.loads((root / "automation/hq_semantic_contract_paths.json").read_text(encoding="utf-8"))
        tasks = contracts((root / "automation/hq_backlog_160.md").read_text(encoding="utf-8"))
        evidence = json.loads((root / "automation/task-evidence.json").read_text(encoding="utf-8"))
        self.assertEqual(1, mapping["schema"])
        # Preserve the original eight independently audited mappings while
        # permitting additional fully validated semantic contracts.
        mapped = {int(n) for n in mapping["items"]}
        self.assertTrue({22, 41, 47, 49, 51, 52, 55, 109}.issubset(mapped))
        self.assertGreaterEqual(len(mapped), 8)
        for raw_number, item in mapping["items"].items():
            number = int(raw_number)
            with self.subTest(task=number):
                self.assertEqual(tasks[number]["owner"], item["owner"])
                self.assertNotIn(item["owner"], item["support"])
                self.assertTrue(set(item["support"]) - set(tasks[number]["support"]) == set(),
                                "Supporting team must be authorized in canonical contract")
                self.assertTrue(item["acceptance"] and item["unmet"])
                self.assertTrue(item["source_paths"], "Observed candidate source paths required")
                if not item["test_paths"]:
                    self.assertEqual(item["state"], "CANDIDATE",
                                     "Unmapped regression must never be READY")
                    self.assertTrue(any("검사" in gap or "테스트" in gap
                                        for gap in item["unmet"]),
                                    "Missing test mapping must be explicitly documented")
                for path in item["source_paths"] + item["test_paths"]:
                    self.assertTrue((root / path).is_file(), f"Missing real mapped path for #{number}: {path}")
                self.assertIn(item["state"], {"CANDIDATE", "BLOCKED", "CODE_VERIFIED", "READY"})
                if item["state"] == "READY":
                    self.assertEqual("PASS", item["independent_team15"])
                    self.assertTrue(item.get("independent_ci_url"), "READY requires exact CI proof")
                    self.assertRegex(item.get("independent_ci_sha", ""), r"^[0-9a-f]{40}$")
                if item["state"] == "CODE_VERIFIED":
                    self.assertEqual("code_verified", evidence[raw_number]["status"])
                    self.assertTrue(item.get("evidence_run"))
        self.assertEqual("BLOCKED", mapping["items"]["47"]["state"])
        self.assertIn("오답", " ".join(mapping["items"]["47"]["unmet"]))
        self.assertIn("즐겨찾기", " ".join(mapping["items"]["47"]["unmet"]))
        self.assertNotIn(mapping["items"]["47"]["forbidden_mapping"], mapping["items"]["47"]["source_paths"])
        self.assertIn("phase3/learning.py", mapping["items"]["49"]["source_paths"])
        self.assertEqual("BLOCKED", mapping["items"]["22"]["state"])
        self.assertEqual("CANDIDATE", mapping["items"]["51"]["state"])
        self.assertIn(mapping["items"]["54"]["state"], {"CANDIDATE", "CODE_VERIFIED"})
        if mapping["items"]["54"]["state"] == "CODE_VERIFIED":
            self.assertEqual("code_verified", evidence["54"]["status"])
            self.assertTrue(mapping["items"]["54"].get("evidence_run"))
        self.assertIn("scripts/team12_missing_recording_script.py", mapping["items"]["54"]["test_paths"])
        self.assertIn("automation/verify_task54.py", mapping["items"]["54"]["test_paths"])
        # READY is allowed only when the independent queue gate accepts it;
        # the old blanket assertion made READY=0 an enforced permanent state.
        from hq_traffic_lights import readiness
        actual = readiness(tasks, evidence, mapping, root)
        declared = {int(n) for n, x in mapping["items"].items() if x["state"] == "READY"}
        dispatched = {x["task"] for x in actual["dispatchable"]}
        self.assertEqual(declared, dispatched, actual["invalid_ready"])


    def test_new_reviewed_ready_task_reaches_real_dispatch_without_curated_id(self):
        import tempfile
        from pathlib import Path
        c = contracts(sample())
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "new-feature.py").write_text("pass\n")
            (root / "test_new_feature.py").write_text("pass\n")
            record = {
                "owner": "12", "support": ["13"], "state": "READY",
                "source_paths": ["new-feature.py"],
                "test_paths": ["test_new_feature.py"],
                "independent_team15": "PASS",
                "independent_ci_url": "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/123", "independent_ci_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            }
            registry = {"schema": 1, "items": {"45": record}}
            assignment = next_assignment("12", c, {}, registry=registry, root=root)
            self.assertEqual(assignment["task_number"], 45)
            self.assertEqual(assignment["path"], "new-feature.py")
            self.assertEqual(assignment["source"], "independently_reviewed_READY_registry")
            self.assertEqual(assignment["independent_test_paths"], ["test_new_feature.py"])
            self.assertEqual(assignment["mode"], "develop")
            self.assertNotIn((45, "new-feature.py"), CURATED_TARGETS["12"])
            self.assertIsNone(next_assignment("13", c, {}, registry=registry, root=root))
            # Never reimplement a commit pending independent CI.
            pending = {"45": {"status": "in_progress", "independent_review": "pass"}}
            self.assertNotEqual((next_assignment("12", c, pending, registry=registry, root=root) or {}).get("task_number"), 45)
            verified = {"45": {"status": "code_verified"}}
            self.assertNotEqual((next_assignment("12", c, verified, registry=registry, root=root) or {}).get("task_number"), 45)
            record["independent_team15"] = "PENDING"
            self.assertNotEqual((next_assignment("12", c, {}, registry=registry, root=root) or {}).get("task_number"), 45)
            record["independent_team15"] = "PASS"
            record["source_paths"] = ["../outside.py"]
            self.assertNotEqual((next_assignment("12", c, {}, registry=registry, root=root) or {}).get("task_number"), 45)

    def test_reviewed_ready_collision_and_retry_limit_are_fail_closed(self):
        import tempfile
        from pathlib import Path
        c = contracts(sample())
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name in ("shared.py", "other.py", "test_shared.py"):
                (root / name).write_text("pass\n")
            def item(number, path):
                return {"owner": "12", "support": ["13"], "state": "READY",
                        "source_paths": [path], "test_paths": ["test_shared.py"],
                        "independent_team15": "PASS",
                        "independent_ci_url": "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/123", "independent_ci_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
            reg = {"schema": 1, "items": {"45": item(45, "shared.py"),
                                          "46": item(46, "shared.py")}}
            self.assertNotEqual((next_assignment("12", c, {}, registry=reg, root=root) or {}).get("task_number"), 45)
            reg["items"]["46"]["source_paths"] = ["other.py"]
            self.assertEqual(next_assignment("12", c, {}, registry=reg, root=root)["task_number"], 45)
            self.assertNotEqual((next_assignment("12", c, {}, failures={"45": {"attempts": 2}},
                                                registry=reg, root=root) or {}).get("task_number"), 45)
            # A multi-file READY is not yet compatible with single-file patch verification.
            reg["items"]["45"]["source_paths"] = ["shared.py", "other.py"]
            reg["items"]["46"]["source_paths"] = ["shared.py"]
            self.assertNotEqual((next_assignment("12", c, {}, registry=reg, root=root) or {}).get("task_number"), 45)

if __name__ == "__main__":
    unittest.main()
