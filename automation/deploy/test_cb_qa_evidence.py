"""Adversarial B evidence provenance tests; synthetic fixtures are NOT real B QA."""
import unittest
from cb_qa_evidence import inspect_evidence, REPO

S = "a" * 40
Q = "b" * 40


def fixture():
    return dict(
        repo=REPO, source_sha=S, qa_sha=Q, trusted_b_login="independent-b",
        source_pr={"state": "open", "user": {"login": "developer"},
                   "head": {"sha": S, "ref": "support/p0-durable-host-handoff-20261031"}},
        qa_pr={"number": 500, "state": "open", "merged": False,
               "user": {"login": "qa-author"},
               "head": {"sha": Q, "ref": "qa/isolated-b"},
               "base": {"sha": S, "ref": "support/p0-durable-host-handoff-20261031"}},
        qa_files=[{"filename": "automation/deploy/test_bqa_security.py", "status": "added"}],
        qa_run={"head_sha": Q, "event": "pull_request", "status": "completed",
                "conclusion": "success", "head_repository": {"full_name": REPO},
                "run_attempt": 1, "pull_requests": [{"number": 500}]},
        qa_reviews=[{"user": {"login": "independent-b"}, "commit_id": Q,
                     "state": "APPROVED", "submitted_at": "2026-11-01T05:00:00Z",
                     "body": f"HS_B_QA_VERDICT status=QA_PASS product_sha={S} qa_sha={Q}"}])


class EvidenceTests(unittest.TestCase):
    def check(self, changes=None):
        data = fixture()
        if changes:
            changes(data)
        return inspect_evidence(**data)

    def test_valid_distinct_b_fixture(self):
        self.assertEqual(self.check()["status"], "QA_PASS")

    def test_same_account_cannot_claim_independence(self):
        self.assertEqual(self.check(lambda d: d.update(trusted_b_login="developer"))["status"], "UNVERIFIED")
        self.assertEqual(self.check(lambda d: d.update(trusted_b_login="qa-author"))["status"], "UNVERIFIED")

    def test_qa_pr_base_must_match_exact_source(self):
        self.assertEqual(self.check(lambda d: d["qa_pr"]["base"].update(sha="c"*40))["status"], "UNVERIFIED")
        self.assertEqual(self.check(lambda d: d["source_pr"]["head"].update(sha="c"*40))["status"], "UNVERIFIED")

    def test_forged_or_stale_run(self):
        self.assertEqual(self.check(lambda d: d["qa_run"].update(head_sha="c"*40))["status"], "UNVERIFIED")
        self.assertEqual(self.check(lambda d: d["qa_run"].update(pull_requests=[{"number": 499}]))["status"], "UNVERIFIED")
        self.assertEqual(self.check(lambda d: d["qa_run"].update(head_repository={"full_name": "evil/repo"}))["status"], "UNVERIFIED")

    def test_no_product_code_modification(self):
        self.assertEqual(self.check(lambda d: d["qa_files"].append({"filename": "automation/ai_agent_runner.py", "status": "modified"}))["status"], "UNVERIFIED")
        self.assertEqual(self.check(lambda d: d["qa_files"][0].update(status="modified"))["status"], "UNVERIFIED")

    def test_review_identity_and_commit(self):
        self.assertEqual(self.check(lambda d: d["qa_reviews"][0]["user"].update(login="someone-else"))["status"], "UNVERIFIED")
        self.assertEqual(self.check(lambda d: d["qa_reviews"][0].update(commit_id="c"*40))["status"], "UNVERIFIED")
        self.assertEqual(self.check(lambda d: d["qa_reviews"][0].update(body="QA_PASS"))["status"], "UNVERIFIED")

    def test_qa_fail_with_independent_review(self):
        def change(d):
            d["qa_run"]["conclusion"] = "failure"
            d["qa_reviews"][0]["state"] = "CHANGES_REQUESTED"
            d["qa_reviews"][0]["body"] = f"HS_B_QA_VERDICT status=QA_FAIL product_sha={S} qa_sha={Q}"
        self.assertEqual(self.check(change)["status"], "QA_FAIL")

    def test_qa_pass_rejects_failed_ci(self):
        self.assertEqual(self.check(lambda d: d["qa_run"].update(conclusion="failure"))["status"], "UNVERIFIED")

    def test_conflicting_reviews(self):
        def change(d):
            d["qa_reviews"].append(dict(d["qa_reviews"][0], state="CHANGES_REQUESTED",
                                        body=f"HS_B_QA_VERDICT status=QA_FAIL product_sha={S} qa_sha={Q}"))
        self.assertEqual(self.check(change)["status"], "UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
