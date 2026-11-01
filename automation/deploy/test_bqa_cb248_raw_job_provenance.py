"""B/15 independent security regressions for PR #248 exact product SHA.

These tests intentionally demand raw job-log provenance before any autonomous
QA_PASS receipt.  They do not change the C implementation or grant A READY.
"""
import unittest

from cb_qa_evidence import inspect_evidence, collect_github_evidence
from test_cb_qa_evidence import fixture, S, Q


class BIndependentEvidenceBoundary(unittest.TestCase):
    def test_01_positive_control_mismatched_qa_sha_is_rejected(self):
        data = fixture()
        data["qa_run"]["head_sha"] = "c" * 40
        self.assertEqual(inspect_evidence(**data)["status"], "UNVERIFIED")

    def test_02_no_raw_test_job_or_log_must_not_be_autoverified(self):
        # An Actions run can be SUCCESS without executing the B QA tests.
        # The GitHub run-summary payload contains no raw Python test evidence.
        data = fixture()
        self.assertNotIn("jobs", data["qa_run"])
        self.assertNotIn("raw_job_logs", data)
        self.assertEqual(
            inspect_evidence(**data)["status"], "UNVERIFIED",
            "Autonomous QA_PASS must require verified test-job/step/raw-log proof, "
            "not only an Actions run summary and an APPROVED review."
        )

    def test_03_unrelated_successful_workflow_is_not_qa_proof(self):
        # A docs-only workflow on the same QA SHA can succeed while the
        # adversarial test suite was never executed.
        data = fixture()
        data["qa_run"]["name"] = "Docs-only metadata"
        data["qa_run"]["path"] = ".github/workflows/docs-only.yml"
        self.assertEqual(
            inspect_evidence(**data)["status"], "UNVERIFIED",
            "Require allowlisted B QA workflow + raw test job evidence."
        )

    def test_04_collector_must_fetch_independent_test_jobs_and_logs(self):
        data = fixture()
        paths = []
        def get(path):
            paths.append(path)
            if path == "/pulls/168": return data["source_pr"]
            if path == "/pulls/500": return data["qa_pr"]
            if path.startswith("/pulls/500/files?"): return data["qa_files"]
            if path == "/actions/runs/123": return data["qa_run"]
            if path.startswith("/pulls/500/reviews?"): return data["qa_reviews"]
            raise AssertionError(path)
        result = collect_github_evidence(
            token="synthetic-not-real", source_pr_number=168,
            qa_pr_number=500, run_id=123, source_sha=S, qa_sha=Q,
            trusted_b_login="independent-b", get_json=get)
        self.assertEqual(
            result["status"], "UNVERIFIED",
            "The controller fetched only PR/review/run summaries, never raw "
            "Actions job logs. A missing log must fail closed."
        )
        self.assertFalse(any("/jobs" in p or "/logs" in p for p in paths))


if __name__ == "__main__":
    unittest.main()
