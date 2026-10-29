#!/usr/bin/env python3
"""Fail closed if the integration CI runner cannot install its pinned Playwright.

Regression context: GitHub Actions 40973272936 failed before tests because
Playwright 1.51.1 rejected ubuntu26.04-x64. Do not classify that as a product
regression or remove browser tests to make the workflow green.
"""
from pathlib import Path
import re

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/integration-validation.yml"
PINNED_RUNNER = re.compile(r"(?m)^    runs-on:\s*ubuntu-24\.04\s*(?:#.*)?$")


def validate_workflow(text: str) -> list[str]:
    failures = []
    validate_job = re.search(r"(?m)^  validate:[ \\t]*$", text)
    if not validate_job:
        failures.append("INTEGRATION_VALIDATE_JOB_MISSING")
        job_body = ""
    else:
        remainder = text[validate_job.end():]
        next_job = re.search(r"(?m)^  [A-Za-z0-9_-]+:[ \\t]*$", remainder)
        job_body = remainder[:next_job.start()] if next_job else remainder
    if not PINNED_RUNNER.search(job_body):
        failures.append("PLAYWRIGHT_RUNNER_MUST_BE_UBUNTU_24_04")
    if "npm ci --prefix phase3 --ignore-scripts" not in text:
        failures.append("PINNED_NODE_DEPENDENCIES_INSTALL_MISSING")
    if "./phase3/node_modules/.bin/playwright install --with-deps chromium" not in text:
        failures.append("CHROMIUM_INSTALL_MISSING")
    if "node phase3/browser-test.cjs" not in text:
        failures.append("BROWSER_REGRESSION_REMOVED")
    return failures


def main() -> int:
    errors = validate_workflow(WORKFLOW.read_text(encoding="utf-8"))
    if errors:
        print("INTEGRATION_RUNNER_BLOCKED:", ", ".join(errors))
        return 1
    print("INTEGRATION_RUNNER_PIN_OK: ubuntu-24.04; browser checks preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
