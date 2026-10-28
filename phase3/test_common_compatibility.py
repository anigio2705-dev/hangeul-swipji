"""Legacy compatibility and candidate status/error contract tests (offline)."""
import unittest
from common_contract import (
    roles_from_legacy, legacy_role_for, validate_state, validate_error_code,
    validate_id, validate_amount_minor,
)


class LegacyContractTests(unittest.TestCase):
    def test_all_legacy_roles_round_trip(self):
        for role in ("learner", "partner", "teacher", "admin"):
            with self.subTest(role=role):
                self.assertEqual(legacy_role_for(roles_from_legacy(role)), role)

    def test_legacy_projection_never_adds_privilege(self):
        self.assertEqual(roles_from_legacy("teacher"), frozenset(("teacher",)))
        self.assertNotIn("learner", roles_from_legacy("teacher"))

    def test_multirole_cannot_be_silently_downgraded(self):
        with self.assertRaises(ValueError):
            legacy_role_for(("learner", "teacher"))

    def test_invalid_legacy_roles_rejected(self):
        for value in (None, "", "owner", ["learner"]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                roles_from_legacy(value)

    def test_booking_and_matching_states(self):
        for domain, states in (("booking", ("reserved", "test_paid", "in_class", "refunded")),
                               ("match", ("idle", "waiting", "offered", "active", "ended")),
                               ("transaction", ("pending", "captured", "partially_refunded"))):
            for state in states:
                self.assertEqual(validate_state(state, domain), state)

    def test_unknown_states_rejected(self):
        for domain, state in (("booking", "active"), ("match", "paid"),
                              ("transaction", "completed"), ("unknown", "reserved")):
            with self.subTest(domain=domain, state=state), self.assertRaises(ValueError):
                validate_state(state, domain)

    def test_error_codes(self):
        self.assertEqual(validate_error_code("FORBIDDEN"), "FORBIDDEN")
        for value in ("", "OK", None, 403):
            with self.assertRaises(ValueError):
                validate_error_code(value)

    def test_shared_id_and_money_boundaries(self):
        self.assertEqual(validate_id("abc-123_def"), "abc-123_def")
        self.assertEqual(validate_amount_minor(10**15), 10**15)
        with self.assertRaises(ValueError):
            validate_amount_minor(True)


if __name__ == "__main__":
    unittest.main()
