"""Task #101: actual Phase3 HTTP + persistent SQLite referral consent."""
import unittest
import server
from test_server import Client, PlatformTests


class ReferralHttpContractTests(unittest.TestCase):
    setUp = PlatformTests.setUp
    tearDown = PlatformTests.tearDown
    register = PlatformTests.register
    book = PlatformTests.book
    action = PlatformTests.action
    finish = PlatformTests.finish

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
            db.execute("UPDATE users SET role=? WHERE id=?", ("admin", self.o["id"]))
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

    def test_booking_referral_cannot_bypass_role_or_cycle_policy(self):
        with server.connect() as db:
            admin_code = db.execute(
                "SELECT referral_code FROM users WHERE email=?",
                ("admin@example.com",)
            ).fetchone()[0]
        self.assertEqual(400, self.book(referral=admin_code)[0])
        self.assertIsNone(self.parent_of(self.l["id"]))
        # Role-changed inviter must not be accepted by the older booking path.
        with server.connect() as db:
            db.execute("UPDATE users SET role=? WHERE id=?", ("admin", self.o["id"]))
        self.assertEqual(400, self.book(referral=self.referral_code(self.o["id"]))[0])
        with server.connect() as db:
            db.execute("UPDATE users SET role=? WHERE id=?", ("learner", self.o["id"]))
        # Outsider -> learner is valid, but learner -> outsider would form a cycle.
        self.assertEqual(200, self.outsider.call("/api/referrals/link", {
            "referralCode": self.referral_code(self.l["id"])
        })[0])
        self.assertEqual(409, self.book(referral=self.referral_code(self.o["id"]))[0])
        self.assertIsNone(self.parent_of(self.l["id"]))
        # The failed booking must not consume the available slot.
        self.assertEqual(200, self.book()[0])


    def test_revoked_referrer_allows_booking_without_new_reward(self):
        # Task #101: a historical inviter's changed role cannot veto lessons.
        # Historical referral consent remains immutable, but a later role
        # revocation must not deny a learner's otherwise valid lesson booking.
        inviter_code = self.referral_code(self.o["id"])
        status, response = self.learner.call("/api/referrals/link", {
            "referralCode": inviter_code
        })
        self.assertEqual(200, status, response)
        self.assertEqual(self.o["id"], self.parent_of(self.l["id"]))
        with server.connect() as db:
            db.execute("UPDATE users SET role='admin' WHERE id=?", (self.o["id"],))
        # Explicitly submitting a revoked code remains invalid.
        self.assertEqual(400, self.book(referral=inviter_code)[0])
        status, response = self.book()
        self.assertEqual(200, status, response)
        first_bid = response["bookingId"]
        with server.connect() as db:
            booked = db.execute("SELECT referrer_id FROM bookings WHERE id=?", (first_bid,)).fetchone()
            snapshot = db.execute("SELECT referral_bps FROM rate_snapshots WHERE booking_id=?", (first_bid,)).fetchone()
            self.assertIsNone(booked["referrer_id"])
            self.assertEqual(0, snapshot["referral_bps"])
            self.assertEqual(0, db.execute("SELECT count(*) FROM ledger").fetchone()[0])
        self.assertEqual(self.o["id"], self.parent_of(self.l["id"]))
        # A later restored role affects only NEW booking snapshots.
        with server.connect() as db:
            db.execute("UPDATE users SET role='learner' WHERE id=?", (self.o["id"],))
        status, slot = self.teacher.call("/api/availability", {
            "start": self.clock + 4800, "end": self.clock + 8400
        })
        self.assertEqual(200, status, slot)
        status, response = self.book(slot=slot["slotId"])
        self.assertEqual(200, status, response)
        with server.connect() as db:
            second_bid = response["bookingId"]
            booked = db.execute("SELECT referrer_id FROM bookings WHERE id=?", (second_bid,)).fetchone()
            snapshot = db.execute("SELECT referral_bps FROM rate_snapshots WHERE booking_id=?", (second_bid,)).fetchone()
            self.assertEqual(self.o["id"], booked["referrer_id"])
            self.assertEqual(300, snapshot["referral_bps"])
            self.assertIsNone(db.execute("SELECT referrer_id FROM bookings WHERE id=?", (first_bid,)).fetchone()["referrer_id"])

    def test_revoked_referrer_settlement_and_refund_never_accrue_reward(self):
        # Task #101: eligibility is captured at booking, not recomputed on
        # settlement/refund. Exercise the full simulated attendance and ledger.
        inviter_code = self.referral_code(self.o["id"])
        status, response = self.learner.call("/api/referrals/link", {
            "referralCode": inviter_code
        })
        self.assertEqual(200, status, response)
        with server.connect() as db:
            db.execute("UPDATE users SET role='admin' WHERE id=?", (self.o["id"],))
        status, response = self.book()
        self.assertEqual(200, status, response)
        bid = response["bookingId"]
        self.finish(bid)
        status, settled = self.admin.call("/api/admin/settle", {"bookingId": bid})
        self.assertEqual(200, status, settled)
        self.assertFalse(settled["realPayout"])
        self.assertEqual(0, settled["split"]["referral"])
        with server.connect() as db:
            booking = db.execute("SELECT referrer_id FROM bookings WHERE id=?", (bid,)).fetchone()
            rates = db.execute("SELECT referral_bps FROM rate_snapshots WHERE booking_id=?", (bid,)).fetchone()
            accrual = db.execute("SELECT amount,beneficiary FROM ledger WHERE booking_id=? AND kind='test_referral_accrual'", (bid,)).fetchone()
            self.assertIsNone(booking["referrer_id"])
            self.assertEqual(0, rates["referral_bps"])
            self.assertEqual(0, accrual["amount"])
            self.assertIsNone(accrual["beneficiary"])
        status, case = self.action(self.learner, bid, "dispute", {
            "category": "refund", "reason": "Test revoked inviter refund and ledger reversal"
        })
        self.assertEqual(200, status, case)
        status, refunded = self.admin.call("/api/admin/disputes/" + case["disputeId"], {
            "decision": "refund", "reason": "Test-only refund approved after evidence"
        })
        self.assertEqual(200, status, refunded)
        with server.connect() as db:
            entries = db.execute("SELECT kind,amount FROM ledger WHERE booking_id=?", (bid,)).fetchall()
            totals = {}
            for entry in entries:
                kind = entry["kind"].removesuffix("_reversal")
                totals[kind] = totals.get(kind, 0) + entry["amount"]
            self.assertTrue(entries)
            self.assertTrue(all(value == 0 for value in totals.values()), totals)
            self.assertEqual(self.o["id"], self.parent_of(self.l["id"]))

if __name__ == "__main__":
    unittest.main()
