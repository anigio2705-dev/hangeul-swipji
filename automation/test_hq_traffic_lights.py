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
                       "independent_team15": "PENDING", "independent_ci_url": "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/123", "independent_ci_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
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
                      "independent_ci_url": "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/123", "independent_ci_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
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
                        "independent_ci_url": "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/123", "independent_ci_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
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
            self.assertEqual(out["candidate_supply"]["16"][0]["blockers"], ["independent_ci_reference_missing", "independent_ci_sha_missing"])
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
                "independent_ci_url": "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/123", "independent_ci_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
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
                            "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/123", "independent_ci_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
            reg = {"schema": 1, "items": {"41": record(41), "49": record(49)}}
            result = readiness(c, {}, reg, root)
            self.assertEqual(result["dispatchable_total"], 2)
            self.assertEqual(result["invalid_ready"], [])
            reg["items"]["49"]["editable_path"] = "edit_41.py"
            reg["items"]["49"]["source_paths"].append("edit_41.py")
            collision = readiness(c, {}, reg, root)
            self.assertEqual(collision["dispatchable_total"], 0)
            self.assertEqual({x["task"] for x in collision["invalid_ready"]}, {41, 49})


    def test_candidate_intake_identifies_missing_ci_and_unsupported_js_runner(self):
        c = catalog()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for path in ("feature.py", "test_feature.py", "global-language.js", "test_language.cjs"):
                (root / path).write_text("pass\\n")
            good = {"owner": "14", "state": "CANDIDATE",
                    "source_paths": ["feature.py"], "test_paths": ["test_feature.py"],
                    "independent_team15": "PASS",
                    "independent_ci_url": "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/123",
                    "independent_ci_sha": "a" * 40}
            js = {"owner": "16", "state": "CANDIDATE",
                  "source_paths": ["global-language.js"], "test_paths": ["test_language.cjs"],
                  "independent_team15": "PASS",
                  "independent_ci_url": good["independent_ci_url"],
                  "independent_ci_sha": good["independent_ci_sha"]}
            registry = {"schema": 1, "items": {"101": good, "143": js}}
            result = readiness(c, {}, registry, root)
            self.assertEqual(result["dispatchable_total"], 0)
            self.assertEqual(result["candidate_supply"]["14"][0]["blockers"], [])
            self.assertIn("unsupported_python_unittest_runner",
                          result["candidate_supply"]["16"][0]["blockers"])
            good["independent_ci_sha"] = "unverified"
            blocked = readiness(c, {}, registry, root)
            self.assertIn("independent_ci_sha_missing",
                          blocked["candidate_supply"]["14"][0]["blockers"])

    def test_ready_must_reject_unsupported_executor_before_dispatch(self):
        """A signed READY registry cannot assign JS, workflow, or non-unittest patches to the Python-only runner."""
        c = catalog()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name in ("global-language.js", "test_language.cjs",
                         "feature.py", "spec_feature.py", "test_feature.py"):
                (root / name).write_text("pass\\n")
            (root / "automation").mkdir()
            (root / "automation" / "protected.py").write_text("pass\\n")
            record = {"owner": "16", "state": "READY",
                      "source_paths": ["feature.py"], "test_paths": ["test_feature.py"],
                      "independent_team15": "PASS",
                      "independent_ci_url": "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/123",
                      "independent_ci_sha": "a" * 40}
            registry = {"schema": 1, "items": {"143": record}}
            self.assertEqual(readiness(c, {}, registry, root)["dispatchable_total"], 1)
            for source, test in (
                ("global-language.js", "test_language.cjs"),
                ("feature.py", "spec_feature.py"),
                ("automation/protected.py", "test_feature.py"),
            ):
                with self.subTest(source=source, test=test):
                    record["source_paths"] = [source]
                    record["test_paths"] = [test]
                    verdict = readiness(c, {}, registry, root)
                    self.assertEqual(verdict["dispatchable_total"], 0)
                    self.assertIn("unsupported_python_unittest_runner",
                                  verdict["invalid_ready"][0]["reason"])

    def test_ready_symlink_alias_must_not_edit_protected_or_alias_test(self):
        """READY paths cannot use in-repo symlinks to hide protected targets."""
        c = catalog()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "automation").mkdir()
            (root / "automation" / "protected.py").write_text("pass\n")
            (root / "automation" / "test_protected.py").write_text("pass\n")
            (root / "feature.py").write_text("pass\n")
            (root / "test_feature.py").write_text("pass\n")
            record = {"owner": "16", "state": "READY",
                      "source_paths": ["feature.py"],
                      "test_paths": ["test_feature.py"],
                      "independent_team15": "PASS",
                      "independent_ci_url":
                          "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/123",
                      "independent_ci_sha": "a" * 40}
            registry = {"schema": 1, "items": {"143": record}}
            self.assertEqual(readiness(c, {}, registry, root)["dispatchable_total"], 1)
            for alias, target in (("feature.py", "automation/protected.py"),
                                  ("test_feature.py", "automation/test_protected.py")):
                with self.subTest(alias=alias):
                    path = root / alias
                    path.unlink()
                    path.symlink_to(target)
                    verdict = readiness(c, {}, registry, root)
                    self.assertEqual(verdict["dispatchable_total"], 0)
                    self.assertIn("symlink_or_aliased_path",
                                  verdict["invalid_ready"][0]["reason"])
                    path.unlink()
                    path.write_text("pass\n")

    def test_ready_must_have_exact_ci_sha_not_only_green_url(self):
        c = catalog()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "feature.py").write_text("pass\\n")
            (root / "test_feature.py").write_text("pass\\n")
            record = {"owner": "14", "state": "READY",
                      "source_paths": ["feature.py"], "test_paths": ["test_feature.py"],
                      "independent_team15": "PASS",
                      "independent_ci_url": "https://github.com/anigio2705-dev/hangeul-swipji/actions/runs/123"}
            registry = {"schema": 1, "items": {"101": record}}
            out = readiness(c, {}, registry, root)
            self.assertEqual(out["dispatchable_total"], 0)
            self.assertIn("exact_ci_sha", out["invalid_ready"][0]["reason"])
            record["independent_ci_sha"] = "a" * 40
            self.assertEqual(readiness(c, {}, registry, root)["dispatchable_total"], 1)

    def test_blocked_owners_receive_repair_intake_without_ready_promotion(self):
        """#22/#47 must be routed for evidence repair even when READY=0."""
        c = catalog()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for path in ("instant.py", "test_instant.py", "progress.js", "test_progress.js"):
                (root / path).write_text("placeholder\\n")
            registry = {"schema": 1, "items": {
                "22": {"owner": "13", "state": "BLOCKED",
                       "source_paths": ["instant.py"], "test_paths": ["test_instant.py"],
                       "unmet": ["403 unauthorized participant regression"]},
                "47": {"owner": "12", "state": "BLOCKED",
                       "source_paths": ["progress.js"], "test_paths": ["test_progress.js"],
                       "unmet": ["cross-account progress restoration"]},
                "101": {"owner": "14", "state": "CANDIDATE",
                        "source_paths": ["instant.py"], "test_paths": ["test_instant.py"],
                        "unmet": ["independent QA"]},
            }}
            out = readiness(c, {}, registry, root)
            self.assertEqual(out["dispatchable_total"], 0)
            self.assertEqual(out["blocked_repair_next"]["13"], 22)
            self.assertEqual(out["blocked_repair_next"]["12"], 47)
            self.assertEqual(out["intake_next"]["13"], {"task": 22, "lane": "BLOCKED_REPAIR"})
            self.assertEqual(out["intake_next"]["12"], {"task": 47, "lane": "BLOCKED_REPAIR"})
            self.assertEqual(out["intake_next"]["14"], {"task": 101, "lane": "CANDIDATE_REVIEW"})
            self.assertIsNone(out["intake_next"]["11"])
            repair = out["blocked_repair_supply"]["13"][0]
            self.assertEqual(repair["owner"], "13")
            self.assertEqual(repair["source_paths"], ["instant.py"])
            self.assertEqual(repair["test_paths"], ["test_instant.py"])
            self.assertEqual(repair["unmet"], ["403 unauthorized participant regression"])
            self.assertEqual(out["candidate_supply"]["13"], [])
            self.assertEqual(out["blocked"], [22, 47])

    def test_blocked_repair_must_disclose_registry_owner_and_path_mismatch(self):
        """A wrong registry owner or missing source must not look like a clean repair handoff."""
        c = catalog()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "instant.py").write_text("pass\\n")
            (root / "test_instant.py").write_text("pass\\n")
            registry = {"schema": 1, "items": {
                "22": {"owner": "12", "state": "BLOCKED",
                       "source_paths": ["instant.py"],
                       "test_paths": ["test_instant.py"],
                       "independent_team15": "PENDING"},
                "47": {"owner": "12", "state": "BLOCKED",
                       "source_paths": ["missing-progress.js"],
                       "test_paths": ["missing-test.js"],
                       "independent_team15": "PENDING"}
            }}
            result = readiness(c, {}, registry, root)
            self.assertEqual(result["dispatchable_total"], 0)
            self.assertEqual(result["blocked_repair_next"]["13"], 22)
            self.assertEqual(result["blocked_repair_next"]["12"], 47)
            repair22 = result["blocked_repair_supply"]["13"][0]
            repair47 = result["blocked_repair_supply"]["12"][0]
            self.assertIn("owner_mismatch", repair22["repair_blockers"])
            self.assertIn("missing_or_invalid_source_path", repair47["repair_blockers"])
            self.assertIn("missing_or_invalid_test_path", repair47["repair_blockers"])
            self.assertEqual(repair22["owner"], "13")
            self.assertEqual(repair22["registry_owner"], "12")
            self.assertEqual(result["intake_next"]["13"]["lane"], "BLOCKED_REPAIR")


    def test_registry_blocked_overrides_stale_code_verified_ledger(self):
        """#59 cannot disappear from owner repair when ledger and registry disagree."""
        c = catalog()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name in ("audio.py", "test_audio.py"):
                (root / name).write_text("pass\\n")
            registry = {"schema": 1, "items": {
                "59": {"owner": "12", "state": "BLOCKED",
                       "source_paths": ["audio.py"], "test_paths": ["test_audio.py"],
                       "unmet": ["actual UI playback regression not accepted"],
                       "independent_team15": "PENDING"}
            }}
            ledger = {"59": {"status": "code_verified"}}
            result = readiness(c, ledger, registry, root)
            self.assertEqual(result["dispatchable_total"], 0)
            self.assertIn(59, result["blocked"])
            self.assertNotIn(59, result["already_verified"])
            repair = result["blocked_repair_supply"]["12"][0]
            self.assertEqual(repair["task"], 59)
            self.assertIn("ledger_registry_state_conflict", repair["repair_blockers"])
            self.assertEqual(repair["ledger_status"], "code_verified")
            self.assertEqual(result["intake_next"]["12"], {"task": 59, "lane": "BLOCKED_REPAIR"})

if __name__ == "__main__":
    unittest.main()
