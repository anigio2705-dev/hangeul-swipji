"""Independent regression for #101 CI environment blockers, not a READY approval."""
import pathlib
import re
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class Task101CiEnvironmentTests(unittest.TestCase):
    def read(self, name):
        return (ROOT / '.github' / 'workflows' / name).read_text(encoding='utf-8')

    def test_integration_runner_is_playwright_compatible(self):
        y = self.read('integration-validation.yml')
        self.assertRegex(y, r'(?m)^    runs-on: ubuntu-24\\.04$')
        self.assertIn('playwright install --with-deps chromium', y)
        self.assertIn('fetch-depth: 0', y)
        self.assertIn('contents: read', y)

    def test_phase3_runner_preserves_source_history(self):
        y = self.read('phase3-isolated-tests.yml')
        self.assertRegex(y, r'(?m)^    runs-on: ubuntu-24\\.04$')
        self.assertRegex(y, r'(?s)actions/checkout@v4\\n        with:\\n          fetch-depth: 0')
        self.assertIn('playwright install --with-deps chromium', y)
        self.assertIn('contents: read', y)

    def test_original_preservation_commit_is_reachable(self):
        p = subprocess.run(['git', 'show', '7418e32:phase3/content.json'], cwd=ROOT,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        self.assertEqual(p.returncode, 0, p.stderr.decode(errors='replace'))
        self.assertGreater(len(p.stdout), 100)

if __name__ == '__main__':
    unittest.main()
