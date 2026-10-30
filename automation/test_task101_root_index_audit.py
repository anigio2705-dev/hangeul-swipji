"""Independent negative fixtures for read-only #101 root-index protection audit."""
import tempfile
import unittest
from pathlib import Path

from audit_task101_root_index import OBSERVED, PROTECTED, audit, observed_delta


class RootIndexAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # Deliberately synthetic baseline: no production file is rewritten.
        self.original = "".join(before + "\n" for before, _ in OBSERVED).encode()
        self.sources = {path: self.original if path == "index.html" else b"original" for path in PROTECTED}
        for path, data in self.sources.items():
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        handoff = self.root / "scripts/team12_learning_handoff.js"
        handoff.parent.mkdir(parents=True, exist_ok=True)
        handoff.write_text("// fixture", encoding="utf-8")

    def read_baseline(self, path):
        return self.sources[path]

    def apply_observed(self):
        original = self.original.decode()
        for before, after in OBSERVED:
            original = original.replace(before, after, 1)
        (self.root / "index.html").write_text(original, encoding="utf-8")

    def test_exact_five_observed_changes_are_not_approved(self):
        self.apply_observed()
        result = audit(self.root, self.read_baseline)
        self.assertTrue(result["known_delta_only"])
        self.assertFalse(result["approved"])
        self.assertFalse(result["ready"])
        self.assertFalse(result["original_protection_pass"])
        self.assertEqual("PENDING_12_15_HQ2", result["baseline_review_status"])

    def test_extra_unapproved_change_rejected(self):
        self.apply_observed()
        with (self.root / "index.html").open("a", encoding="utf-8") as f:
            f.write("<script>unexpected()</script>")
        result = audit(self.root, self.read_baseline)
        self.assertFalse(result["known_delta_only"])
        self.assertEqual("unrecognized_root_change", result["files"][2]["classification"])

    def test_other_protected_material_changed_is_rejected(self):
        self.apply_observed()
        (self.root / "phase3/content.json").write_bytes(b"tampered")
        self.assertFalse(audit(self.root, self.read_baseline)["known_delta_only"])

    def test_missing_handoff_script_is_rejected(self):
        self.apply_observed()
        (self.root / "scripts/team12_learning_handoff.js").unlink()
        self.assertFalse(audit(self.root, self.read_baseline)["known_delta_only"])

    def test_workflow_fetches_protected_baseline_history(self):
        # The real audit invokes git show 7418e32:<path>. A shallow checkout
        # hides that commit and prevents any machine-readable audit artifact.
        workflow = (Path(__file__).resolve().parents[1]
                    / ".github/workflows/task101-referral-http.yml").read_text(encoding="utf-8")
        self.assertIn("      - uses: actions/checkout@v4\\n        with:\\n          fetch-depth: 0\\n".replace("\\n", "\n"), workflow)

    def test_ambiguous_baseline_anchor_is_rejected(self):
        before = OBSERVED[0][0]
        self.assertEqual((False, "baseline_anchor_missing_or_ambiguous"),
                         observed_delta(self.original + before.encode(), self.original))

    def test_browser_evidence_runs_after_source_failure_without_greenwashing(self):
        # Phase3/free integration must still report failure when the protected
        # original differs, while collecting browser regression evidence.
        for filename in ("phase3-isolated-tests.yml", "integration-validation.yml"):
            workflow = (Path(__file__).resolve().parents[1] / ".github/workflows" / filename).read_text(encoding="utf-8")
            self.assertIn("      - id: source_tests\n        continue-on-error: true\n        run: python -m unittest discover -s phase3 -p 'test_*.py' -v", workflow)
            self.assertIn("      - name: Preserve source-test failure after browser evidence\n        if: ${{ always() && steps.source_tests.outcome != 'success' }}\n        run: exit 1", workflow)


if __name__ == "__main__":
    unittest.main()
