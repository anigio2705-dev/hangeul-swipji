"""B/15 independent exact-SHA HTTP boundary checks for original #110.

No product edits. This only tests the local Phase3 reward explanation route,
not approved business rules, real money, or production authentication.
"""
import unittest

import server
from test_server import Client, PlatformTests


class BIndependentRewardExplanationHttp(unittest.TestCase):
    setUp = PlatformTests.setUp
    tearDown = PlatformTests.tearDown
    register = PlatformTests.register
    book = PlatformTests.book
    booking = PlatformTests.booking

    @staticmethod
    def url(bid):
        return "/api/referrals/reward-explanation?bookingId=" + bid

    def test_01_known_participants_never_receive_reward_amount(self):
        bid = self.booking()
        for client, role in ((self.learner, "learner"), (self.teacher, "teacher"),
                             (self.admin, "platform")):
            with self.subTest(role=role):
                status, data = client.call(self.url(bid))
                self.assertEqual(status, 200, data)
                self.assertEqual(data["view"]["role"], role)
                self.assertEqual(data["view"]["state"], "POLICY_UNVERIFIED")
                self.assertIsNone(data["view"]["hypothetical_candidate_krw"])
                for key in ("approvedPolicy", "realMoneyEnabled"):
                    self.assertIs(data[key], False)
                self.assertIs(data["reviewOnly"], True)

    def test_02_outsider_known_and_unknown_booking_both_denied(self):
        bid = self.booking()
        self.assertEqual(self.outsider.call(self.url(bid))[0], 403)
        self.assertEqual(self.outsider.call(self.url("missingbooking"))[0], 403)

    def test_03_expired_and_revoked_session_do_not_inherit_access(self):
        bid = self.booking()
        old_cookie = self.learner.cookie
        self.assertEqual(Client(self.http.server_port).call(self.url(bid))[0], 401)
        self.learner.call("/api/logout", {})
        self.learner.cookie = old_cookie
        self.assertEqual(self.learner.call(self.url(bid))[0], 401)

    def test_04_teacher_approval_revoked_after_booking(self):
        bid = self.booking()
        with server.connect() as db:
            db.execute("UPDATE users SET approved=0 WHERE id=?", (self.t["id"],))
        self.assertEqual(self.teacher.call(self.url(bid))[0], 403)
        self.assertEqual(self.learner.call(self.url(bid))[0], 200)

    def test_05_slot_teacher_conflict_denies_all_roles(self):
        bid = self.booking()
        _, other = self.register("teacher", "other-bqa-http110")
        with server.connect() as db:
            db.execute("UPDATE bookings SET teacher_id=? WHERE id=?", (other["id"], bid))
        for client in (self.learner, self.teacher, self.admin):
            with self.subTest(client=client):
                self.assertEqual(client.call(self.url(bid))[0], 403)

    def test_06_forged_query_and_double_booking_parameter_fail_closed(self):
        bid = self.booking()
        variants = (
            self.url(bid) + "&role=admin",
            self.url(bid) + "&actorId=" + self.t["id"],
            self.url(bid) + "&paymentVerified=true",
            self.url(bid) + "&policyVersion=approved",
            self.url(bid) + "&bookingId=" + bid,
            "/api/referrals/reward-explanation?bookingId=..%2Fbad",
            "/api/referrals/reward-explanation?bookingId=%00",
        )
        for path in variants:
            with self.subTest(path=path):
                self.assertEqual(self.learner.call(path)[0], 400)

    def test_07_referrer_mismatch_never_authorizes_spoofed_referrer(self):
        with server.connect() as db:
            code = db.execute("SELECT referral_code FROM users WHERE id=?",
                              (self.o["id"],)).fetchone()[0]
        invited, _ = self.register("learner", "invited-bqa-http110", code)
        status, data = self.book(client=invited)
        self.assertEqual(status, 200, data)
        bid = data["bookingId"]
        self.assertEqual(self.outsider.call(self.url(bid))[0], 200)
        with server.connect() as db:
            db.execute("UPDATE bookings SET referrer_id=NULL WHERE id=?", (bid,))
        self.assertEqual(self.outsider.call(self.url(bid))[0], 403)

    def test_08_post_cannot_activate_policy_or_create_ledger(self):
        bid = self.booking()
        with server.connect() as db:
            before = db.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
        status, result = self.learner.call(
            "/api/referrals/reward-explanation",
            {"bookingId": bid, "approvedPolicy": True, "payout": True})
        self.assertEqual(status, 404, result)
        self.assertNotIn("view", result)
        self.assertEqual(self.learner.call(self.url(bid))[0], 200)
        with server.connect() as db:
            after = db.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
