"""Read-only migration compatibility checks against the checked-out legacy SQL schema."""
import pathlib
import sqlite3
import unittest

from common_contract import roles_from_legacy, legacy_role_for, can_teach

SCHEMA = pathlib.Path(__file__).with_name("schema.sql")


class LegacyDatabaseContractTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript(SCHEMA.read_text(encoding="utf-8"))

    def tearDown(self):
        self.db.close()

    def test_legacy_role_column_has_no_multi_role_support(self):
        columns = [row[1] for row in self.db.execute("PRAGMA table_info(users)")]
        self.assertIn("role", columns)
        self.assertNotIn("roles", columns)
        self.assertNotIn("user_roles", [row[0] for row in
            self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")])

    def test_legacy_roles_preserve_exact_permissions(self):
        for role in ("learner", "partner", "teacher", "admin"):
            self.assertEqual(roles_from_legacy(role), frozenset((role,)))
            self.assertEqual(legacy_role_for(roles_from_legacy(role)), role)

    def test_no_implicit_teacher_approval(self):
        self.assertFalse(can_teach(roles_from_legacy("teacher"),
                                   "professional_teacher", "requested"))
        self.assertFalse(can_teach(roles_from_legacy("learner"),
                                   "professional_teacher", "approved"))

    def test_multi_role_requires_explicit_migration(self):
        with self.assertRaises(ValueError):
            legacy_role_for(("learner", "partner"))


if __name__ == "__main__":
    unittest.main()
