"""P0 adversarial QA outbox: no head-of-line blocking or duplicate POST."""
import sqlite3
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import qa_handoff_dispatcher as handoff

REPO = "anigio2705-dev/hangeul-swipji"
SHA1, SHA2 = "a" * 40, "b" * 40


class OutboxFairnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "qa.sqlite3")
        self.root = patch.object(handoff, "DB_ROOT", self.tmp.name + "/")
        self.root.start()
        self.addCleanup(self.root.stop)
        self.conn = sqlite3.connect(self.db)
        self.conn.execute("""CREATE TABLE ci_qa_outbox (
            run_id INTEGER NOT NULL, run_attempt INTEGER NOT NULL,
            pr_number INTEGER NOT NULL, head_sha TEXT NOT NULL,
            branch TEXT NOT NULL, base_ref TEXT NOT NULL,
            ci_completed_at TEXT NOT NULL, received_at INTEGER NOT NULL,
            processing_at INTEGER NOT NULL DEFAULT 0,
            qa_requested_at INTEGER NOT NULL DEFAULT 0,
            state TEXT NOT NULL DEFAULT 'PENDING_B_QA_REQUEST',
            PRIMARY KEY(run_id,run_attempt))""")
        for run, pr, sha in [(101, 168, SHA1), (102, 169, SHA2)]:
            self.conn.execute("""INSERT INTO ci_qa_outbox
                (run_id,run_attempt,pr_number,head_sha,branch,base_ref,
                 ci_completed_at,received_at) VALUES (?,?,?,?,?,?,?,?)""",
                (run, 1, pr, sha, "support/p0-test", "automation/base",
                 "2026-10-31T09:00:00Z", run))
        self.conn.commit()
        self.conn.close()
        self.posts = []
        self.markers = set()
        self.fail_first = False
        self.timeout_first = False

    def state(self, run):
        with sqlite3.connect(self.db) as db:
            return db.execute("SELECT state,next_attempt_at,post_started_at "
                              "FROM ci_qa_outbox WHERE run_id=?", (run,)).fetchone()

    def request(self, path, token, payload=None):
        if payload is not None:
            self.posts.append(payload["body"])
            if "pr=168" in payload["body"] and self.fail_first:
                self.fail_first = False
                raise urllib.error.HTTPError(path, 503, "unavailable", {}, None)
            if "pr=168" in payload["body"] and self.timeout_first:
                self.timeout_first = False
                raise TimeoutError("lost response")
            self.markers.add(payload["body"].split("HS_B_QA_HANDOFF ")[1].split("\\n")[0])
            return {"id": len(self.posts)}
        if "/actions/runs/" in path:
            run = int(path.rsplit("/", 1)[1])
            return {"head_sha": SHA1 if run == 101 else SHA2,
                    "run_attempt": 1, "status": "completed",
                    "conclusion": "success", "event": "pull_request"}
        if "/pulls/" in path:
            pr = int(path.rsplit("/", 1)[1])
            return {"head": {"sha": SHA1 if pr == 168 else SHA2,
                             "ref": "support/p0-test"},
                    "base": {"ref": "automation/base"},
                    "state": "open", "draft": True, "merged": False}
        if "/check-runs?" in path:
            return {"total_count": 1, "check_runs": [
                {"status": "completed", "conclusion": "success"}]}
        if "/comments?" in path:
            return [{"body": "HS_B_QA_HANDOFF " + marker}
                    for marker in self.markers]
        raise AssertionError("unexpected request " + path)

    def dispatch(self, now):
        with patch.object(handoff, "_request", side_effect=self.request):
            return handoff.dispatch_once(self.db, token="test", repo=REPO, now=now)

    def test_503_first_does_not_block_second_or_repost(self):
        self.fail_first = True
        self.assertEqual(self.dispatch(1000), "AMBIGUOUS_POST")
        self.assertEqual(self.dispatch(1001), "B_QA_REQUESTED")
        self.assertEqual(self.state(101)[0], "AMBIGUOUS_POST")
        self.assertEqual(self.state(102)[0], "B_QA_REQUESTED")
        self.assertEqual(len(self.posts), 2)
        # Restart: first item only reconciles marker; no duplicate POST.
        self.assertEqual(self.dispatch(2000), "AMBIGUOUS_POST")
        self.assertEqual(len(self.posts), 2)
        self.markers.add(f"pr=168 sha={SHA1}")
        self.assertEqual(self.dispatch(5000), "RECONCILED")
        self.assertEqual(self.state(101)[0], "B_QA_REQUESTED")
        self.assertEqual(len(self.posts), 2)

    def test_timeout_first_does_not_block_second(self):
        self.timeout_first = True
        self.assertEqual(self.dispatch(1000), "AMBIGUOUS_POST")
        self.assertEqual(self.dispatch(1001), "B_QA_REQUESTED")
        self.assertEqual(len(self.posts), 2)

    def test_pre_post_get_failure_retries_without_starving(self):
        original = self.request
        first = [True]
        def flaky(path, token, payload=None):
            if first[0]:
                first[0] = False
                raise urllib.error.URLError("network offline")
            return original(path, token, payload)
        with patch.object(handoff, "_request", side_effect=flaky):
            self.assertEqual(handoff.dispatch_once(self.db, token="t", repo=REPO, now=1000),
                             "RETRY_WAIT")
        self.assertEqual(self.dispatch(1001), "B_QA_REQUESTED")
        self.assertEqual(self.dispatch(2000), "B_QA_REQUESTED")
        self.assertEqual(len(self.posts), 2)

    def test_crash_after_persisted_post_boundary_no_duplicate(self):
        original = self.request
        def crash(path, token, payload=None):
            if payload is not None:
                raise KeyboardInterrupt("SIGKILL-style interrupted send")
            return original(path, token, payload)
        with patch.object(handoff, "_request", side_effect=crash):
            with self.assertRaises(KeyboardInterrupt):
                handoff.dispatch_once(self.db, token="t", repo=REPO, now=1000)
        self.assertEqual(self.state(101)[0], "POST_IN_FLIGHT")
        self.assertEqual(self.dispatch(1100), "AMBIGUOUS_POST")
        self.assertEqual(self.dispatch(1101), "B_QA_REQUESTED")
        self.assertEqual(len(self.posts), 1)  # only second item's POST

    def test_conflicting_sha_is_stale_no_post(self):
        original = self.request
        def changed(path, token, payload=None):
            result = original(path, token, payload)
            if "/pulls/168" in path:
                result["head"]["sha"] = "c" * 40
            return result
        with patch.object(handoff, "_request", side_effect=changed):
            self.assertEqual(handoff.dispatch_once(self.db, token="t", repo=REPO, now=1000),
                             "STALE_OR_UNVERIFIED")
        self.assertEqual(self.dispatch(1001), "B_QA_REQUESTED")
        self.assertEqual(len(self.posts), 1)

    def test_ambiguous_eventually_dead_letters_without_repost(self):
        self.fail_first = True
        self.assertEqual(self.dispatch(1000), "AMBIGUOUS_POST")
        self.assertEqual(self.dispatch(1001), "B_QA_REQUESTED")
        for i in range(20):
            self.dispatch(10000 + i * 5000)
            if self.state(101)[0] == "DEAD_LETTER":
                break
        self.assertEqual(self.state(101)[0], "DEAD_LETTER")
        self.assertEqual(len(self.posts), 2)


if __name__ == "__main__":
    unittest.main()
