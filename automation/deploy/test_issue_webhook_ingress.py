"""Isolated tests: signed GitHub issue event -> durable queue, no live credentials."""
import hashlib
import hmac
import json
import tempfile
import unittest
import uuid
from pathlib import Path

from continuous_dispatcher import MARKER
from issue_webhook_ingress import InvalidDelivery, process_delivery
from work_request_worker import DurableWorkStore


class SignedIssueWebhookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = str(Path(self.temp.name) / "queue.sqlite3")
        self.secret = "s" * 40
        self.repo = "anigio2705-dev/hangeul-swipji"
        self.event = {"repository": {"full_name": self.repo},
                      "action": "opened", "issue": {"number": 1001,
                      "title": MARKER + " authorized isolated work", "state": "open"}}

    def call(self, *, event=None, secret=None, delivery=None, event_type="issues"):
        body = json.dumps(event if event is not None else self.event).encode()
        signed_with = self.secret if secret is None else secret
        headers = {"X-Hub-Signature-256": "sha256=" + hmac.new(
            signed_with.encode(), body, hashlib.sha256).hexdigest(),
            "X-GitHub-Delivery": delivery or str(uuid.uuid4()),
            "X-GitHub-Event": event_type}
        return process_delivery(body, headers, secret=self.secret,
                                repository=self.repo, db_path=self.db)

    def test_signed_delivery_persists_queue(self):
        self.assertEqual(self.call(), (200, "durably_ingested"))
        store = DurableWorkStore(self.db)
        try:
            self.assertEqual(store.snapshot(1001)["status"], "PENDING")
        finally:
            store.close()

    def test_replay_same_delivery_is_idempotent(self):
        ident = str(uuid.uuid4())
        self.assertEqual(self.call(delivery=ident)[0], 200)
        self.assertEqual(self.call(delivery=ident), (200, "duplicate_delivery"))

    def test_invalid_signature_cannot_enqueue(self):
        with self.assertRaises(InvalidDelivery):
            self.call(secret="wrong")
        self.assertFalse(Path(self.db).exists())

    def test_wrong_repo_rejected(self):
        event = dict(self.event, repository={"full_name": "other/repo"})
        with self.assertRaises(InvalidDelivery):
            self.call(event=event)

    def test_other_events_not_acknowledged_as_work(self):
        self.assertEqual(self.call(event_type="workflow_run"), (202, "ignored_workflow"))
        self.assertFalse(Path(self.db).exists())

    def test_other_active_request_blocks_second(self):
        self.assertEqual(self.call()[0], 200)
        event = dict(self.event, issue={"number": 1002,
                       "title": MARKER + " second", "state": "open"})
        self.assertEqual(self.call(event=event), (409, "multiple_active_requests"))

    def workflow_event(self, *, sha="a" * 40, conclusion="success", run_id=99):
        return {"repository": {"full_name": self.repo}, "action": "completed",
                "workflow_run": {"id": run_id, "run_attempt": 1,
                                 "event": "pull_request", "conclusion": conclusion,
                                 "head_sha": sha, "head_branch": "support/safe-work",
                                 "head_repository": {"full_name": self.repo},
                                 "updated_at": "2026-10-31T08:00:00Z",
                                 "pull_requests": [{"number": 162,
                                     "base": {"ref": "automation/isolated-base"},
                                     "head": {"ref": "support/safe-work",
                                              "sha": sha}}]}}

    def test_ci_success_creates_durable_b_qa_outbox_not_ready(self):
        self.assertEqual(self.call(event=self.workflow_event(),
                                   event_type="workflow_run"),
                         (200, "qa_handoff_queued"))
        import sqlite3
        db = sqlite3.connect(self.db)
        try:
            row = db.execute("SELECT run_id,pr_number,head_sha,state "
                             "FROM ci_qa_outbox").fetchone()
            self.assertEqual(row, (99, 162, "a" * 40, "PENDING_B_QA_REQUEST"))
            self.assertFalse(db.execute(
                "SELECT name FROM sqlite_master WHERE name='work'").fetchone())
        finally:
            db.close()

    def test_ci_red_does_not_create_qa_outbox(self):
        self.assertEqual(self.call(event=self.workflow_event(conclusion="failure"),
                                   event_type="workflow_run"),
                         (202, "ignored_workflow"))
        self.assertFalse(Path(self.db).exists())

    def test_ci_replay_is_idempotent_even_new_delivery_id(self):
        self.assertEqual(self.call(event=self.workflow_event(),
                                   event_type="workflow_run")[0], 200)
        self.assertEqual(self.call(event=self.workflow_event(),
                                   event_type="workflow_run"),
                         (200, "duplicate_ci_event"))

    def test_ci_conflicting_same_run_id_rejected(self):
        self.call(event=self.workflow_event(), event_type="workflow_run")
        with self.assertRaises(InvalidDelivery):
            self.call(event=self.workflow_event(sha="b" * 40),
                      event_type="workflow_run")

    def test_ci_head_mismatch_rejected(self):
        event = self.workflow_event()
        event["workflow_run"]["pull_requests"][0]["head"]["sha"] = "b" * 40
        with self.assertRaises(InvalidDelivery):
            self.call(event=event, event_type="workflow_run")
        self.assertFalse(Path(self.db).exists())

    def test_ci_multi_pr_or_main_target_not_enqueued(self):
        event = self.workflow_event()
        event["workflow_run"]["pull_requests"].append(
            dict(event["workflow_run"]["pull_requests"][0]))
        self.assertEqual(self.call(event=event, event_type="workflow_run"),
                         (202, "ignored_workflow"))
        event = self.workflow_event()
        event["workflow_run"]["pull_requests"][0]["base"]["ref"] = "main"
        self.assertEqual(self.call(event=event, event_type="workflow_run"),
                         (202, "ignored_workflow"))
        self.assertFalse(Path(self.db).exists())

    def test_dispatcher_exact_sha_posts_one_b_qa_request(self):
        import sqlite3
        from unittest.mock import patch
        import qa_handoff_dispatcher as dispatcher
        self.call(event=self.workflow_event(), event_type="workflow_run")
        real_connect = sqlite3.connect
        posted = []

        def fake_api(path, token, payload=None):
            if "/actions/runs/" in path:
                return {"head_sha": "a" * 40, "run_attempt": 1,
                        "status": "completed", "conclusion": "success",
                        "event": "pull_request",
                        "pull_requests": [{"number": 162}],
                        "head_repository": {"full_name": self.repo}}
            if "/check-runs?" in path:
                return {"total_count": 1, "check_runs": [
                    {"status": "completed", "conclusion": "success"}]}
            if "/pulls/" in path:
                return {"head": {"sha": "a" * 40, "ref": "support/safe-work"},
                        "base": {"ref": "automation/isolated-base"},
                        "merged": False, "state": "open", "draft": True}
            if "/comments?" in path:
                return [{"body": x} for x in posted]
            if "/comments" in path and payload:
                posted.append(payload["body"])
                return {"id": 100}
            raise AssertionError(path)

        with patch.object(dispatcher.sqlite3, "connect",
                          side_effect=lambda *a, **kw: real_connect(self.db, **kw)), \
             patch.object(dispatcher, "_request", side_effect=fake_api):
            self.assertEqual(dispatcher.dispatch_once(
                "/var/lib/hangeul-swipji/test.sqlite3",
                token="fake", repo=self.repo, now=1000), "B_QA_REQUESTED")
            self.assertEqual(dispatcher.dispatch_once(
                "/var/lib/hangeul-swipji/test.sqlite3",
                token="fake", repo=self.repo, now=1001), "IDLE")
        self.assertEqual(len(posted), 1)
        self.assertIn("HS_B_QA_HANDOFF pr=162 sha=" + "a" * 40,
                      posted[0])
        db = real_connect(self.db)
        self.assertEqual(db.execute(
            "SELECT state FROM ci_qa_outbox").fetchone()[0], "B_QA_REQUESTED")
        db.close()

    def test_dispatcher_ambiguous_post_never_blindly_retries(self):
        import sqlite3
        import urllib.error
        from unittest.mock import patch
        import qa_handoff_dispatcher as dispatcher
        self.call(event=self.workflow_event(), event_type="workflow_run")
        real_connect = sqlite3.connect
        post_attempts = []
        seen = []

        def fake_api(path, token, payload=None):
            if "/actions/runs/" in path:
                return {"head_sha": "a" * 40, "run_attempt": 1,
                        "status": "completed", "conclusion": "success",
                        "event": "pull_request",
                        "pull_requests": [{"number": 162}],
                        "head_repository": {"full_name": self.repo}}
            if "/check-runs?" in path:
                return {"total_count": 1, "check_runs": [
                    {"status": "completed", "conclusion": "success"}]}
            if "/pulls/" in path:
                return {"head": {"sha": "a" * 40, "ref": "support/safe-work"},
                        "base": {"ref": "automation/isolated-base"},
                        "merged": False, "state": "open", "draft": True}
            if "/comments?" in path:
                return [{"body": x} for x in seen]
            if "/comments" in path and payload:
                post_attempts.append(payload["body"])
                raise urllib.error.HTTPError(path, 503, "ambiguous", {}, None)
            raise AssertionError(path)

        with patch.object(dispatcher.sqlite3, "connect",
                          side_effect=lambda *a, **kw: real_connect(self.db, **kw)), \
             patch.object(dispatcher, "_request", side_effect=fake_api):
            call = lambda now: dispatcher.dispatch_once(
                "/var/lib/hangeul-swipji/test.sqlite3",
                token="fake", repo=self.repo, now=now)
            self.assertEqual(call(1000), "AMBIGUOUS_POST")
            self.assertEqual(call(1200), "AMBIGUOUS_POST")
            self.assertEqual(len(post_attempts), 1)
            seen.append(post_attempts[0])
            self.assertEqual(call(1400), "RECONCILED")
        self.assertEqual(len(post_attempts), 1)

    def test_dispatcher_waits_until_all_ci_checks_green(self):
        import sqlite3
        from unittest.mock import patch
        import qa_handoff_dispatcher as dispatcher
        self.call(event=self.workflow_event(), event_type="workflow_run")
        real_connect = sqlite3.connect
        posted = []

        def fake_api(path, token, payload=None):
            if "/actions/runs/" in path:
                return {"head_sha": "a" * 40, "run_attempt": 1,
                        "status": "completed", "conclusion": "success",
                        "event": "pull_request",
                        "pull_requests": [{"number": 162}],
                        "head_repository": {"full_name": self.repo}}
            if "/pulls/" in path:
                return {"head": {"sha": "a" * 40, "ref": "support/safe-work"},
                        "base": {"ref": "automation/isolated-base"},
                        "merged": False, "state": "open", "draft": True}
            if "/check-runs?" in path:
                return {"total_count": 2, "check_runs": [
                    {"status": "completed", "conclusion": "success"},
                    {"status": "in_progress", "conclusion": None}]}
            if "/comments" in path and payload:
                posted.append(payload)
            return []

        with patch.object(dispatcher.sqlite3, "connect",
                          side_effect=lambda *a, **kw: real_connect(self.db, **kw)), \
             patch.object(dispatcher, "_request", side_effect=fake_api):
            self.assertEqual(dispatcher.dispatch_once(
                "/var/lib/hangeul-swipji/test.sqlite3",
                token="fake", repo=self.repo, now=1000), "CI_NOT_COMPLETE")
        self.assertEqual(posted, [])
        db = real_connect(self.db)
        self.assertEqual(db.execute(
            "SELECT state FROM ci_qa_outbox").fetchone()[0],
            "RETRY_WAIT")
        db.close()

    def test_closed_issue_cancels_existing_lease(self):
        self.assertEqual(self.call()[0], 200)
        store = DurableWorkStore(self.db)
        try:
            lease = store.claim("test-worker")
            self.assertIsNotNone(lease)
        finally:
            store.close()
        event = dict(self.event, issue={"number": 1001,
                       "title": MARKER + " authorized isolated work", "state": "closed"})
        event["action"] = "closed"
        self.assertEqual(self.call(event=event), (200, "durably_cancelled"))
        store = DurableWorkStore(self.db)
        try:
            self.assertEqual(store.snapshot(1001)["status"], "CANCELLED")
        finally:
            store.close()


    def _assert_outbox_fairness(self, mode):
        """A poisoned or unfinished CI row cannot starve a later valid B row."""
        import sqlite3
        import urllib.error
        from unittest.mock import patch
        import qa_handoff_dispatcher as dispatcher
        self.call(event=self.workflow_event(), event_type="workflow_run")
        second = self.workflow_event(sha="b" * 40, run_id=100)
        second["workflow_run"]["head_branch"] = "support/safe-work-b"
        pr = second["workflow_run"]["pull_requests"][0]
        pr["number"] = 163
        pr["head"]["ref"] = "support/safe-work-b"
        self.call(event=second, event_type="workflow_run")
        real_connect = sqlite3.connect
        posts = []

        def fake_api(path, token, payload=None):
            if "/actions/runs/" in path:
                ident = int(path.rsplit("/", 1)[-1])
                return {"head_sha": ("a" if ident == 99 else "b") * 40,
                        "run_attempt": 1, "status": "completed",
                        "conclusion": "success", "event": "pull_request",
                        "pull_requests": [{"number": 162 if ident == 99 else 163}],
                        "head_repository": {"full_name": self.repo}}
            if "/pulls/" in path:
                ident = int(path.rsplit("/", 1)[-1])
                return {"head": {"sha": ("a" if ident == 162 else "b") * 40,
                                 "ref": "support/safe-work" +
                                 ("-b" if ident == 163 else "")},
                        "base": {"ref": "automation/isolated-base"},
                        "merged": False, "state": "open", "draft": True}
            if "/check-runs?" in path:
                incomplete = mode == "ci" and "/commits/" + "a" * 40 in path
                return {"total_count": 1, "check_runs": [
                    {"status": "in_progress" if incomplete else "completed",
                     "conclusion": None if incomplete else "success"}]}
            if "/comments?" in path:
                return []
            if "/comments" in path and payload:
                posts.append(payload["body"])
                if mode == "ambiguous" and "pr=162 " in payload["body"]:
                    raise urllib.error.HTTPError(path, 503, "ambiguous", {}, None)
                return {"id": 100}
            raise AssertionError(path)

        with patch.object(dispatcher.sqlite3, "connect",
                          side_effect=lambda *a, **kw: real_connect(self.db, **kw)), \
             patch.object(dispatcher, "_request", side_effect=fake_api):
            call = lambda t: dispatcher.dispatch_once(
                "/var/lib/hangeul-swipji/test.sqlite3",
                token="fake", repo=self.repo, now=t)
            self.assertEqual(call(1000),
                             "AMBIGUOUS_POST" if mode == "ambiguous"
                             else "CI_NOT_COMPLETE")
            # A is cooled down or isolated, so B must make progress immediately.
            self.assertEqual(call(1001), "B_QA_REQUESTED")
            self.assertEqual(call(1002), "IDLE")
            if mode == "ambiguous":
                self.assertEqual(call(1400), "AMBIGUOUS_POST")
        self.assertEqual(sum("pr=163 " in x for x in posts), 1)
        self.assertEqual(sum("pr=162 " in x for x in posts),
                         1 if mode == "ambiguous" else 0)
        db = real_connect(self.db)
        try:
            states = dict(db.execute(
                "SELECT run_id,state FROM ci_qa_outbox").fetchall())
            self.assertEqual(states[100], "B_QA_REQUESTED")
            self.assertEqual(states[99], "AMBIGUOUS_POST" if mode == "ambiguous"
                             else "RETRY_WAIT")
        finally:
            db.close()

    def test_ambiguous_post_does_not_starve_next_qa_handoff(self):
        self._assert_outbox_fairness("ambiguous")

    def test_incomplete_ci_does_not_starve_next_qa_handoff(self):
        self._assert_outbox_fairness("ci")



if __name__ == "__main__":
    unittest.main()
