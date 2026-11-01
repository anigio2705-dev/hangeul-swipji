import sqlite3
import tempfile
import unittest
from pathlib import Path
from execution_checkpoint import CheckpointConflict, ExecutionJournal


def event(**kwargs):
    row = dict(timestamp="2026-10-31T21:00:00+09:00", instruction_source="Issue #203",
               priority="P0", task_id="#103", owner_role="C", exact_sha="a"*40,
               pr=168, ci_run=41194850464, qa_evidence="", state="CI_PASS",
               blocker="", next_action="request B QA", retry_count=0,
               execution_id="real-run-123")
    row.update(kwargs)
    return row


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "journal.sqlite")
        self.journal = ExecutionJournal(self.path)

    def tearDown(self):
        self.journal.close()
        self.tmp.cleanup()

    def test_idempotent_same_key(self):
        self.assertTrue(self.journal.append("run123:ci:1", event()))
        self.assertFalse(self.journal.append("run123:ci:1", event()))
        self.assertEqual(len(self.journal.replay("real-run-123")), 1)

    def test_conflict_preserves_original(self):
        self.journal.append("run123:ci:1", event())
        with self.assertRaises(CheckpointConflict):
            self.journal.append("run123:ci:1", event(exact_sha="b"*40))
        self.assertEqual(self.journal.latest("real-run-123")["exact_sha"], "a"*40)

    def test_restart_replay(self):
        self.journal.append("run123:ci:1", event())
        self.journal.close()
        self.journal = ExecutionJournal(self.path)
        self.journal.append("run123:qa:1", event(state="QA_REQUESTED", next_action="await B"))
        self.assertEqual([x["state"] for x in self.journal.replay("real-run-123")],
                         ["CI_PASS", "QA_REQUESTED"])
        self.assertEqual(self.journal.latest("real-run-123")["next_action"], "await B")

    def test_qa_and_ready_labels_and_evidence(self):
        for bad in (event(state="READY", owner_role="C", qa_evidence="B PASS"),
                    event(state="QA_PASS", owner_role="C", qa_evidence="B PASS"),
                    event(state="READY", owner_role="A"),
                    event(state="QA_PASS", owner_role="B")):
            with self.assertRaises(CheckpointConflict):
                self.journal.append("bad:1", bad)
        self.assertTrue(self.journal.append("run123:qa:2", event(state="QA_PASS", owner_role="B", qa_evidence="QA-only PR #200")))
        self.assertTrue(self.journal.append("run123:ready:1", event(state="READY", owner_role="A", qa_evidence="QA-only PR #200")))

    def test_invalid_sha_timestamp_retry_and_run(self):
        for bad in (event(exact_sha="MISSING"), event(timestamp="2026-10-31"),
                    event(retry_count=-1), event(ci_run=True)):
            with self.assertRaises(CheckpointConflict):
                self.journal.append("bad:1", bad)

    def test_sqlite_append_only(self):
        self.journal.append("run123:ci:1", event())
        with self.assertRaises(sqlite3.DatabaseError):
            self.journal.db.execute("UPDATE execution_events SET task_id='bad'")
        with self.assertRaises(sqlite3.DatabaseError):
            self.journal.db.execute("DELETE FROM execution_events")

    def test_replay_detects_digest_tampering(self):
        self.journal.append("run123:ci:1", event())
        self.journal.db.execute("DROP TRIGGER execution_events_no_update")
        self.journal.db.execute("UPDATE execution_events SET payload_sha256='bad'")
        with self.assertRaises(CheckpointConflict):
            self.journal.replay("real-run-123")


if __name__ == "__main__":
    unittest.main()
