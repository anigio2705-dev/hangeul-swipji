"""D2 SQLite schema health checks without a live Render deployment."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

REQUIRED = {'users', 'sessions', 'free_lesson_progress',
            'free_quiz_results', 'free_resume_positions'}


class StagingHealthSchemaTests(unittest.TestCase):
    def test_schema_migration_has_all_progress_tables(self):
        schema = (Path(__file__).parent / 'schema.sql').read_text(encoding='utf-8')
        with sqlite3.connect(':memory:') as db:
            db.executescript(schema)
            self.assertEqual(db.execute('PRAGMA quick_check').fetchone()[0], 'ok')
            names = {r[0] for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue(REQUIRED.issubset(names), REQUIRED - names)

    def test_schema_migration_is_idempotent_and_preserves_rows(self):
        schema = (Path(__file__).parent / 'schema.sql').read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / 'progress.sqlite3')
            with sqlite3.connect(path) as db:
                db.executescript(schema)
                db.execute("INSERT INTO users(id,email,password,role,created_at) VALUES(?,?,?,?,?)",
                           ('u-d2', 'd2@example.test', 'dummy-hash', 'student', 1.0))
                db.execute("INSERT INTO free_lesson_progress(user_id,stage,lesson,completed_at) VALUES(?,?,?,?)",
                           ('u-d2', 1, 1, 1.0))
                db.commit()
            with sqlite3.connect(path) as db:
                db.executescript(schema)
                self.assertEqual(db.execute(
                    "SELECT count(*) FROM free_lesson_progress WHERE user_id='u-d2'").fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()
