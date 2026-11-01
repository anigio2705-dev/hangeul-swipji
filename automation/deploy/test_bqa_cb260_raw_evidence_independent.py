"""B/15 independently authored security QA for C PR #260 exact dd9ddf426e.

Synthetic evidence is not independent reviewer identity or host deployment.
"""
import copy
import unittest

from cb_qa_evidence import inspect_evidence, collect_github_evidence
from test_cb_qa_evidence import positive_fixture, set_fail_proof, S, Q


class BIndependentRawEvidenceChecks(unittest.TestCase):
    def verify(self, change=None):
        data = positive_fixture()
        if change:
            change(data)
        return inspect_evidence(**data)["status"]

    def test_01_positive_control_valid_synthetic_job_proof(self):
        self.assertEqual(self.verify(), "QA_PASS")

    def test_02_no_jobs_must_not_grant_pass(self):
        self.assertEqual(self.verify(lambda d: d.pop("qa_jobs")), "UNVERIFIED")

    def test_03_no_raw_log_must_not_grant_pass(self):
        self.assertEqual(self.verify(lambda d: d.pop("raw_job_logs")), "UNVERIFIED")

    def test_04_unrelated_successful_workflow_not_proof(self):
        self.assertEqual(self.verify(lambda d: d["qa_run"].update(
            path=".github/workflows/docs-only.yml", name="Docs-only metadata")),
            "UNVERIFIED")

    def test_05_wrong_job_attempt_rejected(self):
        self.assertEqual(self.verify(lambda d: d["qa_jobs"][0].update(
            run_attempt=2)), "UNVERIFIED")

    def test_06_wrong_job_run_id_rejected(self):
        self.assertEqual(self.verify(lambda d: d["qa_jobs"][0].update(
            run_id=999)), "UNVERIFIED")

    def test_07_wrong_job_sha_rejected(self):
        self.assertEqual(self.verify(lambda d: d["qa_jobs"][0].update(
            head_sha="f" * 40)), "UNVERIFIED")

    def test_08_skipped_b_test_step_rejected(self):
        self.assertEqual(self.verify(lambda d: d["qa_jobs"][0]["steps"][1].update(
            conclusion="skipped")), "UNVERIFIED")

    def test_09_no_unittest_results_despite_success_rejected(self):
        self.assertEqual(self.verify(lambda d: d["raw_job_logs"].update(
            {1001: "2026-11-01T05:00:00Z OK\n"})), "UNVERIFIED")

    def test_10_b_test_log_count_mismatch_rejected(self):
        def corrupt(d):
            d["raw_job_logs"][1001] = d["raw_job_logs"][1001].replace(
                "Ran 1 tests", "Ran 2 tests")
        self.assertEqual(self.verify(corrupt), "UNVERIFIED")

    def test_11_duplicate_b_command_group_rejected(self):
        def corrupt(d):
            d["raw_job_logs"][1001] += d["raw_job_logs"][1001]
        self.assertEqual(self.verify(corrupt), "UNVERIFIED")

    def test_12_qa_fail_requires_raw_b_failure_not_review_only(self):
        def corrupt(d):
            set_fail_proof(d)
            d["qa_reviews"][0]["state"] = "CHANGES_REQUESTED"
            d["qa_reviews"][0]["body"] = (
                f"HS_B_QA_VERDICT status=QA_FAIL product_sha={S} qa_sha={Q}")
            d["raw_job_logs"][1001] = "2026-11-01T05:00:00Z FAILED (failures=1)"
        self.assertEqual(self.verify(corrupt), "UNVERIFIED")

    def test_13_positive_control_valid_synthetic_fail_proof(self):
        def failing(d):
            set_fail_proof(d)
            d["qa_reviews"][0]["state"] = "CHANGES_REQUESTED"
            d["qa_reviews"][0]["body"] = (
                f"HS_B_QA_VERDICT status=QA_FAIL product_sha={S} qa_sha={Q}")
        self.assertEqual(self.verify(failing), "QA_FAIL")

    def test_14_source_sha_spoof_rejected(self):
        self.assertEqual(self.verify(lambda d: d["source_pr"]["head"].update(
            sha="f" * 40)), "UNVERIFIED")

    def test_15_missing_checkout_success_rejected(self):
        self.assertEqual(self.verify(lambda d: d["qa_jobs"][0]["steps"][0].update(
            conclusion="failure")), "UNVERIFIED")

    def test_16_unauthenticated_same_account_reviewer_rejected(self):
        self.assertEqual(self.verify(lambda d: d["qa_reviews"][0]["user"].update(
            login=d["source_pr"]["user"]["login"])), "UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
