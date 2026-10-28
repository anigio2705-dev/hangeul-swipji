"""Non-production SQLite restart and backup/restore integration tests.

Uses the repository's real schema.sql, an isolated temporary DB and sqlite backup.
Does not prove production persistence, backup scheduling or offsite recovery.
"""
import pathlib
import sqlite3
import tempfile
import unittest

from common_compat_adapter import from_legacy_user
from team11_shared_boundary import authorize_provider, authorize_student

SCHEMA = pathlib.Path(__file__).with_name("schema.sql")


class AccountPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.temp.name) / "isolated.db"
        self.db = self.connect()
        self.db.executescript(SCHEMA.read_text(encoding="utf-8"))
        self.db.execute(
            "INSERT INTO users(id,email,password,nickname,role,approved,referral_code,created_at)"
            " VALUES(?,?,?,?,?,?,?,?)",
            ("student-1", "student@example.test", "dummy", "student", "learner", 0, "ref-s", 1.0))
        self.db.execute(
            "INSERT INTO users(id,email,password,nickname,role,approved,referral_code,created_at)"
            " VALUES(?,?,?,?,?,?,?,?)",
            ("teacher-1", "teacher@example.test", "dummy", "teacher", "teacher", 1, "ref-t", 1.0))
        self.db.execute(
            "INSERT INTO slots(id,teacher_id,start,end) VALUES(?,?,?,?)",
            ("slot-1", "teacher-1", 1000.0, 2000.0))
        self.db.execute(
            "INSERT INTO bookings(id,learner_id,teacher_id,slot_id,unit_id,status,price,room,created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            ("booking-1", "student-1", "teacher-1", "slot-1", "unit-1",
             "reserved", 20000, "room-1", 1.0))
        self.db.commit()

    def connect(self, path=None):
        db = sqlite3.connect(str(path or self.db_path))
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_restart_retains_users_profiles_booking(self):
        self.db.close()
        self.db = self.connect()
        learner = self.db.execute("SELECT * FROM users WHERE id='student-1'").fetchone()
        teacher = self.db.execute("SELECT * FROM users WHERE id='teacher-1'").fetchone()
        booking = self.db.execute("SELECT * FROM bookings WHERE id='booking-1'").fetchone()
        self.assertTrue(authorize_student(learner).allowed)
        self.assertTrue(authorize_provider(teacher, "professional_teacher").allowed)
        self.assertEqual(booking["learner_id"], learner["id"])
        self.assertEqual(booking["teacher_id"], teacher["id"])
        self.assertEqual(booking["status"], "reserved")

    def test_restart_retains_provider_revocation(self):
        self.db.execute("UPDATE users SET approved=0 WHERE id='teacher-1'")
        self.db.commit()
        self.db.close()
        self.db = self.connect()
        teacher = self.db.execute("SELECT * FROM users WHERE id='teacher-1'").fetchone()
        self.assertFalse(authorize_provider(teacher, "professional_teacher").allowed)
        self.assertEqual(from_legacy_user(teacher).roles, frozenset(("teacher",)))

    def test_sqlite_backup_and_restore_in_isolated_environment(self):
        backup = pathlib.Path(self.temp.name) / "backup.db"
        restored = pathlib.Path(self.temp.name) / "restored.db"
        with self.connect(backup) as target:
            self.db.backup(target)
        with self.connect(backup) as source, self.connect(restored) as target:
            source.backup(target)
        with self.connect(restored) as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(db.execute("SELECT count(*) FROM bookings").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT role FROM users WHERE id='teacher-1'").fetchone()[0], "teacher")

    def test_duplicate_booking_slot_still_blocked_after_restart(self):
        self.db.close()
        self.db = self.connect()
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(
                "INSERT INTO bookings(id,learner_id,teacher_id,slot_id,unit_id,status,price,room,created_at)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                ("booking-2", "student-1", "teacher-1", "slot-1", "unit-1",
                 "reserved", 20000, "room-2", 2.0))


if __name__ == "__main__":
    unittest.main()
