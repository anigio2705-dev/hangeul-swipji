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


if __name__ == "__main__":
    unittest.main()
