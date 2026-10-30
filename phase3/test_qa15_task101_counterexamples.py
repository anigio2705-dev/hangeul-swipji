"""Independent QA15 counterexamples for #101; branch is forked from PR #153
exact product HEAD 92681fa1f1a6149a362b4f3408308b9e26a286e3.
This file is NOT merged into PR/main and never touches production data.
"""
import unittest
import server
import test_server


class IndependentTask101Counterexamples(unittest.TestCase):
    setUp = test_server.PlatformTests.setUp
    tearDown = test_server.PlatformTests.tearDown
    register = test_server.PlatformTests.register
    book = test_server.PlatformTests.book

    def test_control_valid_referral_booking_snapshot(self):
        code = self.o["referral_code"]
        status, _ = self.learner.call("/api/referrals/link", {"referralCode": code})
        self.assertEqual(200, status)
        status, response = self.book()
        self.assertEqual(200, status, response)
        with server.connect() as db:
            booking = db.execute(
                "SELECT referrer_id FROM bookings WHERE id=?", (response["bookingId"],)
            ).fetchone()
            rate = db.execute(
                "SELECT referral_bps FROM rate_snapshots WHERE booking_id=?",
                (response["bookingId"],),
            ).fetchone()
            self.assertEqual(self.o["id"], booking["referrer_id"])
            self.assertEqual(300, rate["referral_bps"])

    def test_explicit_invalid_referral_code_zero_is_not_omission(self):
        """An explicitly supplied malformed referralCode must be rejected,
        not silently treated as an omitted optional referral code.
        """
        status, response = self.learner.call("/api/bookings", {
            "teacherId": self.t["id"], "slotId": self.slot,
            "unitId": "test-unit", "referralCode": 0,
        })
        self.assertEqual(400, status, response)

    def test_explicit_invalid_referral_code_false_on_signup(self):
        """A non-string explicitly supplied signup referralCode is invalid."""
        newcomer = test_server.Client(self.http.server_port)
        status, response = newcomer.call("/api/register", {
            "email": "qa15-invalid-code@example.com",
            "password": "Password12345!",
            "nickname": "QA15 Invalid",
            "role": "learner",
            "adultConsent": True,
            "referralCode": False,
        })
        self.assertEqual(400, status, response)

    def test_legacy_cycle_does_not_create_reward_on_booking(self):
        """A pre-existing cyclic referral graph must never earn a new award.
        A legitimate learner booking should remain possible with zero reward.
        """
        status, response = self.learner.call("/api/referrals/link", {
            "referralCode": self.o["referral_code"],
        })
        self.assertEqual(200, status, response)
        # Simulate a corrupt/legacy imported row. The live API blocks creating
        # cycles, but persisted data may be imported from older versions.
        with server.connect() as db:
            db.execute("UPDATE users SET referred_by=? WHERE id=?",
                       (self.l["id"], self.o["id"]))
        status, response = self.book()
        self.assertEqual(200, status, response)
        with server.connect() as db:
            booking = db.execute(
                "SELECT referrer_id FROM bookings WHERE id=?", (response["bookingId"],)
            ).fetchone()
            rate = db.execute(
                "SELECT referral_bps FROM rate_snapshots WHERE booking_id=?",
                (response["bookingId"],),
            ).fetchone()
            self.assertIsNone(booking["referrer_id"],
                              "Cyclic historical graph must not earn referral")
            self.assertEqual(0, rate["referral_bps"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
