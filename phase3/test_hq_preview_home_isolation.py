"""Guard the preserved homepage against experimental preview-only UI changes."""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class HomepagePreviewIsolationTests(unittest.TestCase):
    def test_original_homepage_is_byte_identical_to_preserved_baseline(self):
        expected = subprocess.check_output(
            ["git", "show", "7418e32:index.html"], cwd=ROOT
        )
        self.assertEqual(expected, (ROOT / "index.html").read_bytes())

    def test_preview_retains_experimental_ui_without_leaking_to_homepage(self):
        home = (ROOT / "index.html").read_text(encoding="utf-8")
        preview = (ROOT / "index-preview.html").read_text(encoding="utf-8")
        for marker in ("hs-issue4-preview-notice", "data-team12-handoff"):
            self.assertNotIn(marker, home)
            self.assertIn(marker, preview)
        self.assertIn('href="./learn.html"', preview)
        self.assertIn('href="./speaking-platform.html?lang=ko"', preview)
        self.assertIn('src="./scripts/team12_learning_handoff.js"', preview)


if __name__ == "__main__":
    unittest.main()
