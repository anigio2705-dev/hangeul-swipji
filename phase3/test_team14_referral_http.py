"""Task #101: actual Phase3 HTTP + persistent SQLite referral consent."""
import unittest
import server
from test_server import Client, PlatformTests


class ReferralHttpContractTests(unittest.TestCase):
    setUp = PlatformTests.setUp
    tearDown = PlatformTests.tearDown
    register = PlatformTests.register

    def referral_code(self, uid):
        with server.connect() as db:
            return db.execute("SELECT referral_code FROM users WHERE id=?", (uid,)).fetchone()[0]

    def parent_of(self, uid):
        with server.connect() as db:
            return db.execute("SELECT referred_by FROM users WHERE id=?", (uid,)).fetchone()[0]

    def test_all_phase3_roles_and_persistent_booking_column(self):
        for child_role in ("learner", "partner", "teacher"):
            for parent_role in ("learner", "partner", "teacher"):
                with self.subTest(child=child_role, parent=parent_role):
                    child, user = self.register(child_role, "c-" + child_role + parent_role)
                    parent, inviter = self.register(parent_role, "p-" + child_role + parent_role)
                    status, result = child.call("/api/referrals/link", {
                        "referralCode": self.referral_code(inviter["id"])
                    })
                    self.assertEqual(status, 200, result)
                    self.assertTrue(result["linked"])
                    self.assertIs(result["realMoney"], False)
                    self.assertEqual(self.parent_of(user["id"]), inviter["id"])
                    self.assertEqual(child.call("/api/referrals/link", {
                        "referralCode": self.referral_code(inviter["id"])
                    })[1]["alreadyLinked"], True)

    def test_cannot_impersonate_other_account_or_modify_parent(self):
        original = self.referral_code(self.t["id"])
        other = self.referral_code(self.o["id"])
        self.assertEqual(self.learner.call("/api/referrals/link", {
            "referralCode": original, "actorId": self.o["id"]
        })[0], 200)
        self.assertEqual(self.parent_of(self.l["id"]), self.t["id"])
        self.assertEqual(self.outsider.call("/api/referrals/link", {
            "referralCode": other, "actorId": self.l["id"]
        })[0], 409)
        self.assertIsNone(self.parent_of(self.o["id"]))
        self.assertEqual(self.learner.call("/api/referrals/link", {
            "referralCode": other
        })[0], 409)
        self.assertEqual(self.parent_of(self.l["id"]), self.t["id"])

    def test_no_session_admin_self_and_invalid_code_fail_closed(self):
        unauth = Client(self.http.server_port)
        code = self.referral_code(self.t["id"])
        self.assertEqual(unauth.call("/api/referrals/link", {"referralCode": code})[0], 401)
        self.assertEqual(self.admin.call("/api/referrals/link", {"referralCode": code})[0], 403)
        self.assertEqual(self.teacher.call("/api/referrals/link", {
            "referralCode": code
        })[0], 409)
        self.assertEqual(self.learner.call("/api/referrals/link", {
            "referralCode": "missing"
        })[0], 400)
        self.assertIsNone(self.parent_of(self.l["id"]))

    def test_expired_session_and_untrusted_role_rejected(self):
        with server.connect() as db:
            db.execute("UPDATE sessions SET expires=? WHERE user_id=?", (self.clock - 1, self.l["id"]))
        self.assertEqual(self.learner.call("/api/referrals/link", {
            "referralCode": self.referral_code(self.t["id"])
        })[0], 401)
        self.assertIsNone(self.parent_of(self.l["id"]))
        with server.connect() as db:
            db.execute("UPDATE users SET role='admin' WHERE id=?", (self.t["id"],))
        self.assertEqual(self.outsider.call("/api/referrals/link", {
            "referralCode": self.referral_code(self.t["id"])
        })[0], 400)
        self.assertIsNone(self.parent_of(self.o["id"]))

    def test_cycle_and_signup_parent_are_immutable(self):
        self.assertEqual(self.learner.call("/api/referrals/link", {
            "referralCode": self.referral_code(self.t["id"])
        })[0], 200)
        self.assertEqual(self.teacher.call("/api/referrals/link", {
            "referralCode": self.referral_code(self.l["id"])
        })[0], 409)
        self.assertIsNone(self.parent_of(self.t["id"]))
        _, signed = self.register("learner", "signed", self.referral_code(self.t["id"]))
        signed_client = _
        self.assertEqual(signed_client.call("/api/referrals/link", {
            "referralCode": self.referral_code(self.o["id"])
        })[0], 409)
        self.assertEqual(self.parent_of(signed["id"]), self.t["id"])


    def test_signup_referrer_policy_matches_authenticated_link(self):
        # An admin/unknown-role inviter must not bypass the link endpoint's
        # trusted role boundary through the older registration path.
        with server.connect() as db:
            admin_code = db.execute(
                "SELECT referral_code FROM users WHERE email=?",
                ("admin@example.com",)
            ).fetchone()[0]
        for suffix, code in (("admin-inviter", admin_code),):
            status, response = Client(self.http.server_port).call("/api/register", {
                "email": suffix + "@example.com",
                "password": "Password12345!",
                "nickname": "Referral test",
                "role": "learner",
                "adultConsent": True,
                "referralCode": code
            })
            self.assertEqual(400, status, response)
            with server.connect() as db:
                self.assertEqual(0, db.execute(
                    "SELECT count(*) FROM users WHERE email=?", (suffix + "@example.com",)
                ).fetchone()[0])
        # A valid teacher referrer remains accepted at registration.
        _, signed = self.register("learner", "valid-inviter", self.referral_code(self.t["id"]))
        self.assertEqual(self.parent_of(signed["id"]), self.t["id"])
        # A role revoked after signup is no longer a valid inviter.
        with server.connect() as db:
            db.execute("UPDATE users SET role=? WHERE id=?", ("suspended", self.o["id"]))
        status, response = Client(self.http.server_port).call("/api/register", {
            "email": "revoked-inviter@example.com",
            "password": "Password12345!",
            "nickname": "Referral test",
            "role": "learner",
            "adultConsent": True,
            "referralCode": self.referral_code(self.o["id"])
        })
        self.assertEqual(400, status, response)
        with server.connect() as db:
            self.assertEqual(0, db.execute(
                "SELECT count(*) FROM users WHERE email=?",
                ("revoked-inviter@example.com",)
            ).fetchone()[0])

if __name__ == "__main__":
    unittest.main()
