"""P0 task #101: consented, verified four-role referral intake (mock only)."""
import os
import tempfile
import unittest

from team14_persistent import SimError
from team14_referral_store import ReferralStore


class VerifiedReferralRoleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = ReferralStore(os.path.join(self.temp.name, "referrals.sqlite"))

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def resolver(self, roles):
        # Test fixture emulates a trusted server-side account/role lookup.
        return lambda user_id: roles.get(user_id)

    def test_all_four_child_to_inviter_role_combinations(self):
        for child_role in ("teacher", "student"):
            for inviter_role in ("teacher", "student"):
                with self.subTest(child=child_role, inviter=inviter_role):
                    child = "child_" + child_role + "_" + inviter_role
                    inviter = "inviter_" + child_role + "_" + inviter_role
                    roles = {child: child_role, inviter: inviter_role}
                    self.assertTrue(self.store.link_verified(
                        child, inviter, authenticated_actor_id=child,
                        role_lookup=self.resolver(roles)))
                    self.assertEqual(self.store.db.execute(
                        "SELECT parent_id FROM referral_links WHERE student_id=?",
                        (child,)).fetchone()["parent_id"], inviter)

    def test_other_actor_cannot_create_or_replace_referral(self):
        roles = {"child": "student", "inviter": "teacher", "attacker": "student"}
        with self.assertRaises(SimError) as error:
            self.store.link_verified("child", "inviter", "attacker", self.resolver(roles))
        self.assertEqual(error.exception.code, "FORBIDDEN")
        self.assertEqual(self.store.db.execute(
            "SELECT COUNT(*) FROM referral_links").fetchone()[0], 0)

    def test_missing_unverified_or_invalid_roles_rejected_before_write(self):
        for child_role, inviter_role in (
            (None, "teacher"), ("student", None), ("admin", "teacher"),
            ("student", "anonymous"), (True, "teacher"), (["student"], "teacher")
        ):
            with self.subTest(child=child_role, inviter=inviter_role):
                roles = {"child": child_role, "inviter": inviter_role}
                with self.assertRaises(SimError) as error:
                    self.store.link_verified(
                        "child", "inviter", "child", self.resolver(roles))
                self.assertEqual(error.exception.code, "FORBIDDEN")
        self.assertEqual(self.store.db.execute(
            "SELECT COUNT(*) FROM referral_links").fetchone()[0], 0)

    def test_resolver_must_be_callable_and_fail_closed(self):
        for lookup in (None, {}, "teacher"):
            with self.subTest(lookup=lookup):
                with self.assertRaises(SimError) as error:
                    self.store.link_verified("child", "inviter", "child", lookup)
                self.assertEqual(error.exception.code, "VALIDATION_ERROR")
        def unavailable(_user_id):
            raise RuntimeError("account store unavailable")
        with self.assertRaises(SimError) as error:
            self.store.link_verified("child", "inviter", "child", unavailable)
        self.assertEqual(error.exception.code, "FORBIDDEN")
        self.assertEqual(self.store.db.execute(
            "SELECT COUNT(*) FROM referral_links").fetchone()[0], 0)

    def test_verified_replay_immutable_parent_and_cycle_protection(self):
        roles = {"child": "teacher", "inviter": "student",
                 "other": "teacher"}
        lookup = self.resolver(roles)
        self.assertTrue(self.store.link_verified("child", "inviter", "child", lookup))
        self.assertFalse(self.store.link_verified("child", "inviter", "child", lookup))
        with self.assertRaises(SimError):
            self.store.link_verified("child", "other", "child", lookup)
        with self.assertRaises(SimError):
            self.store.link_verified("inviter", "child", "inviter", lookup)
        with self.assertRaises(SimError):
            self.store.link_verified("child", "child", "child", lookup)
        self.assertEqual(self.store.db.execute(
            "SELECT COUNT(*) FROM referral_links").fetchone()[0], 1)

    def test_verified_link_award_remains_mock_and_not_approved(self):
        roles = {"child": "student", "inviter": "teacher"}
        self.store.link_verified("child", "inviter", "child", self.resolver(roles))
        award = self.store.award("event1", "child", "lesson1", 10000)
        self.assertEqual(award["recipients"], [
            {"user_id": "inviter", "amount_krw": 300}])
        self.assertFalse(award["real_money"])
        self.assertFalse(award["policy_approved"])
        self.assertFalse(award["payment_enabled"])


if __name__ == "__main__":
    unittest.main()
