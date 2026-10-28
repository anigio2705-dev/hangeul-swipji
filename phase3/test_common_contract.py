"""Offline, side-effect-free shared contract regression tests."""
import unittest
from common_contract import (
    validate_id, validate_roles, can_teach,
    validate_referral_edge, validate_amount_minor,
)


class ContractTests(unittest.TestCase):
    def test_multiple_roles(self):
        self.assertEqual(validate_roles(["learner", "teacher", "partner"]),
                         frozenset(("learner", "teacher", "partner")))

    def test_unknown_duplicate_or_empty_role(self):
        for value in ([], ["learner", "learner"], ["owner"], "learner", [None]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_roles(value)

    def test_teacher_kind_and_approval(self):
        self.assertTrue(can_teach(["learner", "teacher"], "professional_teacher", "approved"))
        self.assertFalse(can_teach(["learner", "partner"], "professional_teacher", "approved"))
        self.assertFalse(can_teach(["teacher"], "professional_teacher", "requested"))
        self.assertTrue(can_teach(["partner"], "conversation_partner", "approved"))

    def test_invalid_teaching_kind(self):
        with self.assertRaises(ValueError):
            can_teach(["teacher"], "unknown", "approved")

    def test_referral_identity(self):
        self.assertEqual(validate_referral_edge("user_1", "user_2"), ("user_1", "user_2"))
        for a, b in (("x", "x"), ("", "b"), ("a", "../bad")):
            with self.subTest(a=a, b=b), self.assertRaises(ValueError):
                validate_referral_edge(a, b)

    def test_minor_unit_money(self):
        self.assertEqual(validate_amount_minor(0), 0)
        for value in (True, -1, 1.5, "100", 10**16):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_amount_minor(value)

    def test_invalid_id(self):
        for value in ("", "a/b", None, "a" * 129):
            with self.assertRaises(ValueError):
                validate_id(value)


if __name__ == "__main__":
    unittest.main()
