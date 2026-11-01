"""Independent B-only static regression for isolated PR #278 intake contract.
No authenticated Actions run or QA_PASS is implied.
Run: python -m unittest discover -s experiments/b-independent-qa -p 'test_intake_278.py' -v
"""
import pathlib
import re
import unittest

WORKFLOW = pathlib.Path(__file__).resolve().parents[2] / ".github/workflows/b-qa-handoff-intake.yml"

class Intake278IndependentContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")
    def test_workflow_only_exposes_manual_trigger(self):
        self.assertIn("workflow_dispatch:", self.source)
        self.assertNotIn("push:", self.source)
        self.assertNotIn("schedule:", self.source)
    def test_receipt_not_misrepresented_as_verified(self):
        self.assertIn("QA_RECEIVED_CANDIDATE", self.source)
        self.assertIn('"task_contract_verified":False', self.source)
        self.assertIn('"qa_independent_verified":False', self.source)
        self.assertNotIn('"status":"QA_PASS"', self.source)
    def test_pr_sha_and_source_are_checked(self):
        for token in ('p["head"]["sha"]!=sha', 'p["state"]!="open"', 'p["base"]["repo"]["full_name"]!=repo', 'p["head"]["repo"]["full_name"]!=repo'):
            self.assertIn(token, self.source)
    def test_task_number_bounds_only(self):
        self.assertIn("1<=int(task_id)<=160", self.source)
    def test_receipt_artifact_upload(self):
        self.assertIn("actions/upload-artifact@v4", self.source)
        self.assertIn("qa-intake-receipt.json", self.source)
    def test_unverified_task_to_pr_binding_is_missing(self):
        self.assertIn("task_contract_verified", self.source)
        # Explicitly fail until authoritative 160-task ledger lookup is implemented.
        self.fail("BLOCKED: TASK_ID/PRODUCT_PR binding is not verified against authoritative 160-task ledger.")
    def test_authenticated_b_verdict_is_missing(self):
        # Explicitly fail until a separate independent B QA-only verdict and verifier exist.
        self.fail("BLOCKED: No B QA-only run, qa-verdict.json or authenticated A-side intake verifier.")

if __name__ == "__main__":
    unittest.main()
