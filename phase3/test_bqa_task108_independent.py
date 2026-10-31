"""B/15 QA-only #108: independent HTTP/SQLite/identity adversarial tests.

Pinned product PR #177 SHA 7cacebac90ebdc350333659326417fc3678d96ec.
No main, external service, live payments, or operational database.
"""
import http.client
import unittest

import server
from test_server import Client, PlatformTests


class BIndependentTask108Tests(unittest.TestCase):
    setUp = PlatformTests.setUp
    tearDown = PlatformTests.tearDown
    register = PlatformTests.register

    def status(self, client, query=""):
        return client.call("/api/referrals/status" + query)

    def assert_no_money(self, state):
        for key in ("realMoney", "paymentEnabled", "policyApproved"):
            self.assertIs(state[key], False)
        self.assertIs(state["canChange"], False)

    def test_unauthenticated_and_admin_status_denied(self):
        self.assertEqual(401, self.status(Client(self.http.server_port))[0])
        self.assertEqual(403, self.status(self.admin)[0])
        self.assertEqual(200, self.status(self.learner)[0])

    def test_query_user_id_spoof_does_not_cross_account_boundary(self):
        for client, own, other in ((self.learner, self.l, self.t),
                                   (self.teacher, self.t, self.l)):
            status, state = self.status(client, "?userId=" + other["id"] +
                                       "&actorId=" + other["id"])
            self.assertEqual(200, status)
            self.assertEqual(own["referral_code"], state["referralCode"])
            self.assertNotIn(other["referral_code"], str(state))
            self.assert_no_money(state)

    def test_actor_id_in_link_payload_is_ignored(self):
        code = self.t["referral_code"]
        status, result = self.learner.call("/api/referrals/link",
            {"referralCode": code, "userId": self.o["id"], "actorId": self.o["id"]})
        self.assertEqual(200, status, result)
        self.assertTrue(self.status(self.learner)[1]["linked"])
        self.assertFalse(self.status(self.outsider)[1]["linked"])
        with server.connect() as db:
            self.assertEqual(self.t["id"], db.execute(
                "SELECT referred_by FROM users WHERE id=?", (self.l["id"],)
            ).fetchone()[0])
            self.assertIsNone(db.execute(
                "SELECT referred_by FROM users WHERE id=?", (self.o["id"],)
            ).fetchone()[0])
            self.assertEqual(0, db.execute("SELECT count(*) FROM ledger").fetchone()[0])

    def test_immutable_parent_even_after_repeated_conflicting_request(self):
        first = self.learner.call("/api/referrals/link",
                                  {"referralCode": self.t["referral_code"]})
        self.assertEqual(200, first[0])
        for _ in range(3):
            self.assertEqual(409, self.learner.call("/api/referrals/link",
                {"referralCode": self.o["referral_code"]})[0])
            self.assertEqual(200, self.learner.call("/api/referrals/link",
                {"referralCode": self.t["referral_code"]})[0])
        state = self.status(self.learner)[1]
        self.assertTrue(state["linked"])
        self.assertEqual(self.t["nickname"], state["inviter"]["nickname"])
        self.assert_no_money(state)

    def test_admin_and_self_referral_never_bind(self):
        self.assertEqual(403, self.admin.call("/api/referrals/link",
            {"referralCode": self.t["referral_code"]})[0])
        self.assertEqual(409, self.learner.call("/api/referrals/link",
            {"referralCode": self.l["referral_code"]})[0])
        self.assertFalse(self.status(self.learner)[1]["linked"])

    def test_signup_referral_persists_across_new_session_without_reward(self):
        new_client, new_user = self.register("learner", "bqa108fresh",
                                              self.o["referral_code"])
        state = self.status(new_client)[1]
        self.assertTrue(state["linked"])
        self.assertEqual(self.o["nickname"], state["inviter"]["nickname"])
        login = Client(self.http.server_port)
        code, _ = login.call("/api/login", {
            "email": "bqa108fresh@example.com", "password": "Password12345!"})
        self.assertEqual(200, code)
        self.assertEqual(new_user["referral_code"],
                         self.status(login)[1]["referralCode"])
        with server.connect() as db:
            self.assertEqual(0, db.execute("SELECT count(*) FROM ledger").fetchone()[0])

    def test_revoked_inviter_history_read_only(self):
        self.assertEqual(200, self.learner.call("/api/referrals/link",
            {"referralCode": self.o["referral_code"]})[0])
        with server.connect() as db:
            db.execute("UPDATE users SET role='admin' WHERE id=?", (self.o["id"],))
        self.assertTrue(self.status(self.learner)[1]["linked"])
        self.assertEqual(400, self.teacher.call("/api/referrals/link",
            {"referralCode": self.o["referral_code"]})[0])
        self.assert_no_money(self.status(self.learner)[1])

    def test_read_only_html_and_signup_prefill_contract(self):
        with open(server.ROOT / "referral-center.html", encoding="utf-8") as f:
            page = f.read()
        self.assertIn("credentials:\"same-origin\"", page)
        self.assertIn("encodeURIComponent(codeFromLink)", page)
        self.assertIn('byId("relationship").textContent', page)
        self.assertIn('byId("connect").disabled=state.linked', page)
        self.assertNotIn("innerHTML", page)
        with open(server.ROOT / "app.js", encoding="utf-8") as f:
            app = f.read()
        self.assertIn("new URLSearchParams(location.search).get('ref')", app)
        self.assertIn("if(signup&&/^[0-9a-f]{10}$/.test(invited||'')", app)


if __name__ == "__main__":
    unittest.main()
