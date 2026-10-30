"""Task #101 independent four-role-pair HTTP acceptance, no real-money actions.

The canonical backlog requires four teacher/learner referral directions.  These
checks exercise the actual Phase3 HTTP session and SQLite database rather than
only a pure referral simulator.  Passing is NOT a team15/HQ2 READY approval.
"""
import unittest

import server
from test_server import PlatformTests


class Task101FourPairAcceptance(unittest.TestCase):
    setUp = PlatformTests.setUp
    tearDown = PlatformTests.tearDown
    register = PlatformTests.register

    def check_pair(self, inviter_role, referred_role):
        label = inviter_role + "-to-" + referred_role
        _inviter_client, inviter = self.register(inviter_role, "inviter-" + label)
        referred_client, referred = self.register(referred_role, "referred-" + label)
        code = inviter["referral_code"]
        status, payload = referred_client.call(
            "/api/referrals/link", {"referralCode": code}
        )
        self.assertEqual(200, status, payload)
        self.assertTrue(payload["linked"])
        self.assertIs(payload["realMoney"], False)
        with server.connect() as db:
            parent = db.execute(
                "SELECT referred_by FROM users WHERE id=?", (referred["id"],)
            ).fetchone()[0]
            self.assertEqual(inviter["id"], parent)
            self.assertEqual(0, db.execute("SELECT count(*) FROM ledger").fetchone()[0])
        status, replay = referred_client.call(
            "/api/referrals/link", {"referralCode": code}
        )
        self.assertEqual(200, status, replay)
        self.assertTrue(replay["alreadyLinked"])
        with server.connect() as db:
            self.assertEqual(
                inviter["id"],
                db.execute("SELECT referred_by FROM users WHERE id=?", (referred["id"],)).fetchone()[0],
            )

    def test_teacher_refers_teacher(self):
        self.check_pair("teacher", "teacher")

    def test_teacher_refers_learner(self):
        self.check_pair("teacher", "learner")

    def test_learner_refers_teacher(self):
        self.check_pair("learner", "teacher")

    def test_learner_refers_learner(self):
        self.check_pair("learner", "learner")

    def test_second_inviter_cannot_replace_first(self):
        first, inviter = self.register("teacher", "first-inviter")
        second, other = self.register("learner", "second-inviter")
        child, referred = self.register("learner", "one-referred")
        self.assertEqual(200, child.call(
            "/api/referrals/link", {"referralCode": inviter["referral_code"]}
        )[0])
        status, _ = child.call(
            "/api/referrals/link", {"referralCode": other["referral_code"]}
        )
        self.assertEqual(409, status)
        with server.connect() as db:
            self.assertEqual(inviter["id"], db.execute(
                "SELECT referred_by FROM users WHERE id=?", (referred["id"],)
            ).fetchone()[0])
            self.assertEqual(0, db.execute("SELECT count(*) FROM ledger").fetchone()[0])

    def test_two_account_cycle_rejected_without_side_effects(self):
        first_client, first = self.register("teacher", "cycle-first")
        second_client, second = self.register("learner", "cycle-second")
        self.assertEqual(200, second_client.call(
            "/api/referrals/link", {"referralCode": first["referral_code"]}
        )[0])
        status, _ = first_client.call(
            "/api/referrals/link", {"referralCode": second["referral_code"]}
        )
        self.assertEqual(409, status)
        with server.connect() as db:
            self.assertIsNone(db.execute(
                "SELECT referred_by FROM users WHERE id=?", (first["id"],)
            ).fetchone()[0])
            self.assertEqual(0, db.execute("SELECT count(*) FROM ledger").fetchone()[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
