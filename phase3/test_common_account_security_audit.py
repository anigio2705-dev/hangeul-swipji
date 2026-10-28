"""Team11 independent audit of legacy schema and shared authorization boundary.

Tests only a fresh in-memory SQLite database, never production data.
"""
import pathlib
import sqlite3
import unittest

from common_compat_adapter import from_legacy_user, matching_side
from team11_shared_boundary import authorize_provider, authorize_student

SCHEMA = pathlib.Path(__file__).with_name("schema.sql")


class AccountSecurityAuditTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA.read_text(encoding="utf-8"))

    def tearDown(self):
        self.db.close()

    def insert_user(self, uid, role, approved=0):
        self.db.execute(
            "INSERT INTO users(id,email,password,nickname,role,approved,referral_code,created_at)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (uid, uid + "@example.test", "not-a-real-password", "test",
             role, approved, "ref-" + uid, 0.0),
        )
        return self.db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()

    def test_real_schema_legacy_roles_round_trip(self):
        for role in ("learner", "partner", "teacher", "admin"):
            row = self.insert_user("user-" + role, role)
            self.assertEqual(from_legacy_user(row).roles, frozenset((role,)))

    def test_unapproved_teacher_and_partner_blocked(self):
        for role, kind in (("teacher", "professional_teacher"),
                           ("partner", "conversation_partner")):
            row = self.insert_user("user-" + role, role, 0)
            self.assertFalse(authorize_provider(row, kind).allowed)

    def test_approved_teacher_and_partner_allowed(self):
        for role, kind in (("teacher", "professional_teacher"),
                           ("partner", "conversation_partner")):
            row = self.insert_user("user-" + role, role, 1)
            self.assertTrue(authorize_provider(row, kind).allowed)

    def test_legacy_role_cannot_elevate_to_learner(self):
        row = self.insert_user("user-teacher", "teacher", 1)
        self.assertFalse(authorize_student(row).allowed)
        self.assertFalse(matching_side(from_legacy_user(row), "learner"))

    def test_legacy_role_column_rejects_unknown_and_multirole(self):
        for role in ("teacher,admin", "root", "learner,partner"):
            with self.subTest(role=role), self.assertRaises(sqlite3.IntegrityError):
                self.insert_user("invalid-" + str(len(role)), role)

    def test_unique_email_and_referral_code_constraints(self):
        self.insert_user("first", "learner")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(
                "INSERT INTO users(id,email,password,nickname,role,referral_code,created_at)"
                " VALUES(?,?,?,?,?,?,?)",
                ("second", "first@example.test", "x", "test", "different", "ref-second", 0.0),
            )

    def test_sessions_and_audit_are_persisted_in_schema(self):
        tables = {row[0] for row in self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"users", "sessions", "audit", "bookings", "ledger"} <= tables)


if __name__ == "__main__":
    unittest.main()
