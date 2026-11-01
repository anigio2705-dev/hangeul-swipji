"""Offline adversarial tests for CI polling fallback (no GitHub credentials)."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ci_poll_fallback as fallback


class CIPollFallbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = str(Path(self.temp.name) / "outbox.db")
        self.sha = "a" * 40
        self.run = {"id": 100, "run_attempt": 1, "event": "pull_request",
                    "status": "completed", "conclusion": "success",
                    "head_sha": self.sha, "head_branch": "support/test",
                    "head_repository": {"full_name": fallback.REPO},
                    "updated_at": "2026-10-31T08:00:00Z",
                    "pull_requests": [{"number": 168}]}
        self.pr = {"state": "open", "merged": False, "draft": True,
                   "head": {"sha": self.sha, "ref": "support/test",
                            "repo": {"full_name": fallback.REPO}},
                   "base": {"ref": "automation/isolated"}}
        self.responses = {"runs": [self.run], "pr": self.pr}
        self.calls = []

    def fetch(self, path, token):
        self.calls.append(path)
        if "/actions/runs?" in path:
            return {"workflow_runs": self.responses["runs"]}
        if "/pulls/168" in path:
            return self.responses["pr"]
        raise AssertionError(path)

    def poll(self, **kw):
        original = fallback._persist_ci_qa_event
        def persist(event, *, db_path):
            return original(event, db_path=self.db)
        with patch.object(fallback, "_persist_ci_qa_event", side_effect=persist):
            return fallback.poll_once("/var/lib/hangeul-swipji/outbox.db",
                                      token="fake", fetch=self.fetch, **kw)

    def test_success_durable_outbox_and_replay(self):
        first = self.poll()
        self.assertEqual(first["queued"], 1)
        self.assertTrue(first["scan_complete"])
        self.assertEqual(self.poll()["duplicates"], 1)
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*),MIN(head_sha),MIN(state) FROM ci_qa_outbox"
            ).fetchone(), (1, self.sha, "PENDING_B_QA_REQUEST"))

    def test_stale_sha_cannot_queue(self):
        self.responses["pr"]["head"]["sha"] = "b" * 40
        self.assertEqual(self.poll()["queued"], 0)
        self.assertFalse(Path(self.db).exists())

    def test_wrong_repo_or_main_base_cannot_queue(self):
        self.responses["pr"]["head"]["repo"]["full_name"] = "attacker/other"
        self.assertEqual(self.poll()["queued"], 0)
        self.responses["pr"]["head"]["repo"]["full_name"] = fallback.REPO
        self.responses["pr"]["base"]["ref"] = "main"
        self.assertEqual(self.poll()["queued"], 0)
        self.assertFalse(Path(self.db).exists())

    def test_non_draft_cannot_queue(self):
        self.responses["pr"]["draft"] = False
        self.assertEqual(self.poll()["queued"], 0)

    def test_failed_ci_cannot_queue(self):
        self.run["conclusion"] = "failure"
        self.assertEqual(self.poll()["queued"], 0)

    def test_invalid_repo_or_db_rejected_before_network(self):
        with self.assertRaises(ValueError):
            self.poll(repo="attacker/other")
        with self.assertRaises(ValueError):
            fallback.poll_once("/tmp/outbox.db", token="fake", fetch=self.fetch)
        self.assertEqual(self.calls, [])

    def test_parent_traversal_rejected_before_network_or_write(self):
        for outside in (
                "/var/lib/hangeul-swipji/../attacker-owned/ci.sqlite",
                "/var/lib/hangeul-swipji/../../tmp/attacker-ci.sqlite"):
            with self.subTest(outside=outside):
                with self.assertRaises(ValueError):
                    fallback.poll_once(outside, token="fake", fetch=self.fetch)
        self.assertEqual(self.calls, [])

    def test_symlink_escape_rejected_before_network(self):
        with tempfile.TemporaryDirectory() as outside:
            with tempfile.TemporaryDirectory() as root:
                link = Path(root) / "escape"
                link.symlink_to(outside, target_is_directory=True)
                from qa_handoff_dispatcher import _trusted_db_path
                with self.assertRaises(ValueError):
                    _trusted_db_path(str(link / "ci.sqlite"), root=root)

    def test_full_page_at_limit_fails_closed(self):
        self.responses["runs"] = [dict(self.run, conclusion="failure") for _ in range(100)]
        with self.assertRaises(fallback.PollIncomplete):
            self.poll(pages=1)

    def test_network_failure_not_acknowledged(self):
        def broken(path, token):
            raise TimeoutError("GitHub unavailable")
        with patch.object(fallback, "github_get", side_effect=broken):
            with self.assertRaises(TimeoutError):
                fallback.poll_once("/var/lib/hangeul-swipji/outbox.db",
                                   token="fake", fetch=broken)
        self.assertFalse(Path(self.db).exists())

    def test_malformed_response_fails_closed(self):
        self.responses["runs"] = "not a list"
        with self.assertRaises(fallback.PollIncomplete):
            self.poll()

    def test_same_sha_new_run_queues_once_per_run_not_qa_pass(self):
        self.responses["runs"] = [self.run, dict(self.run, id=101)]
        self.assertEqual(self.poll()["queued"], 2)
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM ci_qa_outbox WHERE state='PENDING_B_QA_REQUEST'"
            ).fetchone()[0], 2)


if __name__ == "__main__":
    unittest.main()
