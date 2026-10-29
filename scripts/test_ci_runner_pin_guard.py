"""Independent negative regression tests for the Playwright CI runner pin."""
import unittest
from scripts.ci_runner_pin_guard import validate_workflow

BASE = """name: Free education and teaching integration checks
jobs:
  validate:
    runs-on: ubuntu-24.04
    steps:
      - run: npm ci --prefix phase3 --ignore-scripts
      - run: ./phase3/node_modules/.bin/playwright install --with-deps chromium
      - run: node phase3/browser-test.cjs
"""


class RunnerPinRegressionTests(unittest.TestCase):
    def test_pinned_ubuntu_2404_passes(self):
        self.assertEqual([], validate_workflow(BASE))

    def test_ubuntu_latest_fails(self):
        self.assertIn("PLAYWRIGHT_RUNNER_MUST_BE_UBUNTU_24_04",
                      validate_workflow(BASE.replace("ubuntu-24.04", "ubuntu-latest")))

    def test_ubuntu_2604_fails(self):
        self.assertIn("PLAYWRIGHT_RUNNER_MUST_BE_UBUNTU_24_04",
                      validate_workflow(BASE.replace("ubuntu-24.04", "ubuntu-26.04")))

    def test_comment_cannot_spoof_pin(self):
        sample = BASE.replace("runs-on: ubuntu-24.04",
                              "runs-on: ubuntu-latest # runs-on: ubuntu-24.04")
        self.assertIn("PLAYWRIGHT_RUNNER_MUST_BE_UBUNTU_24_04",
                      validate_workflow(sample))

    def test_removing_browser_checks_fails(self):
        self.assertIn("BROWSER_REGRESSION_REMOVED",
                      validate_workflow(BASE.replace("node phase3/browser-test.cjs", "echo skip")))

    def test_missing_install_fails(self):
        self.assertIn("CHROMIUM_INSTALL_MISSING",
                      validate_workflow(BASE.replace("playwright install --with-deps chromium", "echo skip")))

    def test_missing_validate_job_fails(self):
        self.assertIn("INTEGRATION_VALIDATE_JOB_MISSING",
                      validate_workflow(BASE.replace("  validate:", "  bypass:")))


if __name__ == "__main__":
    unittest.main()
