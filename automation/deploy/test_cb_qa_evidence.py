"""Adversarial B evidence provenance tests; synthetic fixtures are NOT real B QA."""
import unittest
from cb_qa_evidence import inspect_evidence, collect_github_evidence, REPO

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


def positive_fixture():
    """Synthetic exact-run B job and bounded raw log proof, never a real QA."""
    data = fixture()
    data["qa_run"].update(
        id=123, name="P0 isolated host infrastructure static checks",
        path=".github/workflows/p0-host-infra-static.yml")
    data["qa_jobs"] = [{
        "id": 1001, "run_id": 123, "run_attempt": 1, "head_sha": Q,
        "name": "host-infra-static", "status": "completed", "conclusion": "success",
        "steps": [
            {"name": "Run actions/checkout@v4", "conclusion": "success"},
            {"name": "Run independently added B QA-only regression tests (if present)",
             "conclusion": "success"}]}]
    data["raw_job_logs"] = {1001: (
        "2026-11-01T05:00:00Z ##[group]Run if compgen -G 'automation/deploy/test_bqa_*.py' >/dev/null; then\n"
        "2026-11-01T05:00:01Z ##[endgroup]\n"
        "2026-11-01T05:00:02Z test_positive (test_bqa_security.Case.test_positive) ... ok\n"
        "2026-11-01T05:00:03Z Ran 1 tests in 0.001s\n"
        "2026-11-01T05:00:04Z OK\n"
        "2026-11-01T05:00:05Z ##[group]Run next step\n")}
    return data


def set_fail_proof(data):
    data["qa_run"]["conclusion"] = "failure"
    data["qa_jobs"][0]["conclusion"] = "failure"
    data["qa_jobs"][0]["steps"][1]["conclusion"] = "failure"
    data["raw_job_logs"][1001] = (
        "2026-11-01T05:00:00Z ##[group]Run if compgen -G 'automation/deploy/test_bqa_*.py' >/dev/null; then\n"
        "2026-11-01T05:00:01Z ##[endgroup]\n"
        "2026-11-01T05:00:02Z test_positive (test_bqa_security.Case.test_positive) ... FAIL\n"
        "2026-11-01T05:00:03Z Ran 1 tests in 0.001s\n"
        "2026-11-01T05:00:04Z FAILED (failures=1)\n"
        "2026-11-01T05:00:05Z ##[group]Run next step\n")


class EvidenceTests(unittest.TestCase):
    def check(self, changes=None):
        data = positive_fixture()
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

    def test_missing_or_malformed_pr_list_fails_closed(self):
        self.assertEqual(self.check(lambda d: d["qa_run"].update(pull_requests=None))["status"], "UNVERIFIED")
        self.assertEqual(self.check(lambda d: d["qa_run"].pop("pull_requests"))["status"], "UNVERIFIED")

    def test_no_product_code_modification(self):
        self.assertEqual(self.check(lambda d: d["qa_files"].append({"filename": "automation/ai_agent_runner.py", "status": "modified"}))["status"], "UNVERIFIED")
        self.assertEqual(self.check(lambda d: d["qa_files"][0].update(status="modified"))["status"], "UNVERIFIED")

    def test_review_identity_and_commit(self):
        self.assertEqual(self.check(lambda d: d["qa_reviews"][0]["user"].update(login="someone-else"))["status"], "UNVERIFIED")
        self.assertEqual(self.check(lambda d: d["qa_reviews"][0].update(commit_id="c"*40))["status"], "UNVERIFIED")
        self.assertEqual(self.check(lambda d: d["qa_reviews"][0].update(body="QA_PASS"))["status"], "UNVERIFIED")

    def test_qa_fail_with_independent_review(self):
        def change(d):
            set_fail_proof(d)
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


    def test_no_raw_job_or_log_never_grants_qa_pass(self):
        self.assertEqual(self.check(lambda d: d.pop("qa_jobs"))["status"], "UNVERIFIED")
        self.assertEqual(self.check(lambda d: d.pop("raw_job_logs"))["status"], "UNVERIFIED")

    def test_unrelated_workflow_or_job_attempt_fails_closed(self):
        self.assertEqual(self.check(lambda d: d["qa_run"].update(path=".github/workflows/docs.yml"))["status"], "UNVERIFIED")
        self.assertEqual(self.check(lambda d: d["qa_jobs"][0].update(run_attempt=2))["status"], "UNVERIFIED")
        self.assertEqual(self.check(lambda d: d["qa_jobs"][0].update(run_id=999))["status"], "UNVERIFIED")

    def test_successful_job_without_executed_b_tests_rejected(self):
        self.assertEqual(self.check(lambda d: d["raw_job_logs"].update({1001: "2026-11-01T05:00:00Z OK"}))["status"], "UNVERIFIED")
        self.assertEqual(self.check(lambda d: d["qa_jobs"][0]["steps"][1].update(conclusion="skipped"))["status"], "UNVERIFIED")

    def test_qa_fail_requires_raw_failing_b_tests(self):
        def missing_log(d):
            set_fail_proof(d)
            d["qa_reviews"][0]["state"] = "CHANGES_REQUESTED"
            d["qa_reviews"][0]["body"] = f"HS_B_QA_VERDICT status=QA_FAIL product_sha={S} qa_sha={Q}"
            d["raw_job_logs"][1001] = "2026-11-01T05:00:00Z FAILED (failures=1)"
        self.assertEqual(self.check(missing_log)["status"], "UNVERIFIED")

class GitHubReadOnlyCollectionTests(unittest.TestCase):
    def test_fetches_only_expected_rest_evidence(self):
        data = positive_fixture()
        paths = []
        def get(path):
            paths.append(path)
            if path == "/pulls/168": return data["source_pr"]
            if path == "/pulls/500": return data["qa_pr"]
            if path.startswith("/pulls/500/files?"): return data["qa_files"]
            if path == "/actions/runs/123": return data["qa_run"]
            if path.startswith("/actions/runs/123/jobs?"): return {"total_count": 1, "jobs": data["qa_jobs"]}
            if path.startswith("/pulls/500/reviews?"): return data["qa_reviews"]
            raise AssertionError(path)
        result = collect_github_evidence(
            token="fixture-not-a-real-token", source_pr_number=168,
            qa_pr_number=500, run_id=123, source_sha=S, qa_sha=Q,
            trusted_b_login="independent-b", get_json=get,
            get_text=lambda path: data["raw_job_logs"][1001] if path == "/actions/jobs/1001/logs" else None)
        self.assertEqual(result["status"], "QA_PASS")
        self.assertEqual(len(paths), 6)
        self.assertTrue(all(path.startswith("/") and "POST" not in path for path in paths))

    def test_untrusted_same_account_is_not_qa(self):
        data = fixture()
        def get(path):
            if path == "/pulls/168": return data["source_pr"]
            if path == "/pulls/500": return data["qa_pr"]
            if "/files?" in path: return data["qa_files"]
            if "/reviews?" in path: return data["qa_reviews"]
            return data["qa_run"]
        self.assertEqual(collect_github_evidence(
            token="fixture", source_pr_number=168, qa_pr_number=500,
            run_id=123, source_sha=S, qa_sha=Q,
            trusted_b_login="developer", get_json=get)["status"], "UNVERIFIED")

    def test_review_pagination_must_be_complete(self):
        data = fixture()
        def get(path):
            if path == "/pulls/168": return data["source_pr"]
            if path == "/pulls/500": return data["qa_pr"]
            if "/files?" in path: return data["qa_files"]
            if "/reviews?" in path: return data["qa_reviews"] * 100
            return data["qa_run"]
        self.assertEqual(collect_github_evidence(
            token="fixture", source_pr_number=168, qa_pr_number=500,
            run_id=123, source_sha=S, qa_sha=Q,
            trusted_b_login="independent-b", get_json=get)["status"], "UNVERIFIED")

    def test_invalid_request_never_fetches(self):
        def fail(_): raise AssertionError("network should not be touched")
        self.assertEqual(collect_github_evidence(
            token="fixture", source_pr_number=True, qa_pr_number=500,
            run_id=123, source_sha=S, qa_sha=Q,
            trusted_b_login="independent-b", get_json=fail)["status"], "UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
