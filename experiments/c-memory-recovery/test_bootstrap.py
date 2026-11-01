import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from bootstrap import resume_gate

OLD = 'a' * 40
NEW = 'b' * 40


class RecoveryGateTests(unittest.TestCase):
    def test_sha_change_after_restart_blocks_old_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, 'memory.db')
            before = resume_gate(db, '140', OLD, OLD, OLD, True, True, True, True)
            self.assertEqual(before['state'], 'VERIFIED_READY_TO_RESUME')
            self.assertFalse(before['execution_allowed'])
            script = "import json,sys;from bootstrap import resume_gate;print(json.dumps(resume_gate(sys.argv[1],'140','%s','%s','%s',True,True,True,True)))" % (OLD, NEW, OLD)
            p = subprocess.run([sys.executable, '-c', script, db], cwd=os.path.dirname(__file__), capture_output=True, text=True, check=True)
            after = json.loads(p.stdout)
            self.assertEqual(after['state'], 'RECOVERY_BLOCKED')
            self.assertFalse(after['execution_allowed'])
            self.assertEqual(after['revision'], 2)
            self.assertEqual(sqlite3.connect(db).execute("SELECT state FROM resume_decisions WHERE task_id='140'").fetchone()[0], 'RECOVERY_BLOCKED')

    def test_missing_verification_is_not_permission(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, 'memory.db')
            self.assertEqual(resume_gate(db, '140', OLD)['state'], 'RECOVERED_UNVERIFIED')
            self.assertEqual(resume_gate(db, '140', OLD, OLD, OLD, False, True, True, True)['state'], 'RECOVERED_UNVERIFIED')
            self.assertEqual(resume_gate(db, '140', OLD, OLD, OLD, True, True, False, True)['state'], 'RECOVERED_UNVERIFIED')
            self.assertEqual(resume_gate(db, '140', OLD, OLD, OLD, True, True, True, True, conflict=True)['state'], 'RECOVERY_BLOCKED')

    def test_stale_writer_cannot_reverse_sha_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, 'memory.db')
            first = resume_gate(db, '123', OLD, OLD, OLD, True, True, True, True)
            blocked = resume_gate(db, '123', OLD, NEW, OLD, True, True, True, True)
            self.assertEqual(blocked['state'], 'RECOVERY_BLOCKED')
            stale = resume_gate(db, '123', OLD, OLD, OLD, True, True, True, True,
                                expected_revision=first['revision'])
            self.assertEqual(stale['state'], 'RECOVERY_BLOCKED')
            self.assertFalse(stale['execution_allowed'])
            self.assertEqual(stale['revision'], blocked['revision'])
            self.assertEqual(sqlite3.connect(db).execute("SELECT state,revision FROM resume_decisions").fetchone(), ('RECOVERY_BLOCKED', 2))

    def test_no_revision_or_even_current_revision_cannot_unblock(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, 'memory.db')
            blocked = resume_gate(db, '123', OLD, NEW, OLD, True, True, True, True)
            for rev in (None, blocked['revision']):
                result = resume_gate(db, '123', OLD, OLD, OLD, True, True, True, True,
                                     expected_revision=rev)
                self.assertEqual(result['state'], 'RECOVERY_BLOCKED')
                self.assertFalse(result['execution_allowed'])
                self.assertEqual(result['revision'], blocked['revision'])

    def test_revision_required_for_nonblocking_updates(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, 'memory.db')
            first = resume_gate(db, '123', OLD)
            unversioned = resume_gate(db, '123', OLD, OLD, OLD, True, True, True, True)
            self.assertEqual(unversioned['reason'], 'REVISION_REQUIRED')
            self.assertEqual(unversioned['revision'], first['revision'])
            updated = resume_gate(db, '123', OLD, OLD, OLD, True, True, True, True,
                                  expected_revision=first['revision'])
            self.assertEqual(updated['revision'], first['revision'] + 1)
            self.assertFalse(updated['execution_allowed'])
            stale = resume_gate(db, '123', OLD, OLD, OLD, True, True, True, True,
                                expected_revision=first['revision'])
            self.assertEqual(stale['reason'], 'STALE_REVISION')

    def test_legacy_schema_migrates_without_authorization(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, 'memory.db')
            with sqlite3.connect(db) as cx:
                cx.execute('CREATE TABLE resume_decisions (task_id TEXT PRIMARY KEY, saved_sha TEXT NOT NULL, current_sha TEXT, qa_sha TEXT, state TEXT NOT NULL, reason TEXT NOT NULL, checked_at TEXT NOT NULL)')
                cx.execute('INSERT INTO resume_decisions VALUES (?,?,?,?,?,?,?)', ('123', OLD, OLD, OLD, 'VERIFIED_READY_TO_RESUME', 'LEGACY', 'now'))
            blocked = resume_gate(db, '123', OLD, NEW, OLD, True, True, True, True)
            self.assertEqual(blocked['state'], 'RECOVERY_BLOCKED')
            self.assertEqual(blocked['revision'], 2)
            self.assertFalse(blocked['execution_allowed'])


if __name__ == '__main__':
    unittest.main()
