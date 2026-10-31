"""#108 authenticated referral sharing/status and immutable relationship integration."""
import http.client
import unittest

import server
from test_server import Client, PlatformTests


class Task108ReferralCenterTests(unittest.TestCase):
    setUp = PlatformTests.setUp
    tearDown = PlatformTests.tearDown
    register = PlatformTests.register

    def code(self, user):
        return user["referral_code"]

    def status(self, client):
        return client.call("/api/referrals/status")

    def test_own_status_only_and_no_financial_authorization(self):
        status, response = self.status(self.learner)
        self.assertEqual(200, status, response)
        self.assertEqual(self.code(self.l), response["referralCode"])
        self.assertFalse(response["linked"])
        self.assertIsNone(response["inviter"])
        for field in ("canChange", "realMoney", "paymentEnabled", "policyApproved"):
            self.assertIs(response[field], False)
        self.assertNotIn(self.code(self.t), str(response))
        self.assertEqual(401, self.status(Client(self.http.server_port))[0])
        self.assertEqual(403, self.status(self.admin)[0])

    def test_consent_link_replay_and_immutable_parent(self):
        code = self.code(self.t)
        status, result = self.learner.call("/api/referrals/link", {"referralCode": code})
        self.assertEqual(200, status, result)
        self.assertTrue(result["linked"])
        status, state = self.status(self.learner)
        self.assertEqual(200, status, state)
        self.assertTrue(state["linked"])
        self.assertEqual(self.t["nickname"], state["inviter"]["nickname"])
        self.assertIs(state["canChange"], False)
        self.assertEqual(200, self.learner.call("/api/referrals/link", {"referralCode": code})[0])
        self.assertEqual(409, self.learner.call(
            "/api/referrals/link", {"referralCode": self.code(self.o)})[0])
        with server.connect() as db:
            self.assertEqual(self.t["id"], db.execute(
                "SELECT referred_by FROM users WHERE id=?", (self.l["id"],)).fetchone()[0])
            self.assertEqual(0, db.execute("SELECT count(*) FROM ledger").fetchone()[0])

    def test_signup_link_existing_account_and_relogin_persist(self):
        client, user = self.register("learner", "referred108", self.code(self.t))
        status, state = self.status(client)
        self.assertEqual(200, status, state)
        self.assertTrue(state["linked"])
        self.assertEqual(self.t["nickname"], state["inviter"]["nickname"])
        self.assertEqual(409, client.call(
            "/api/referrals/link", {"referralCode": self.code(self.o)})[0])
        relogin = Client(self.http.server_port)
        self.assertEqual(200, relogin.call("/api/login", {
            "email": "referred108@example.com", "password": "Password12345!"})[0])
        self.assertEqual(user["referral_code"], self.status(relogin)[1]["referralCode"])
        self.assertTrue(self.status(relogin)[1]["linked"])

    def test_self_cycle_and_admin_cannot_bind(self):
        self.assertEqual(409, self.learner.call(
            "/api/referrals/link", {"referralCode": self.code(self.l)})[0])
        self.assertEqual(200, self.learner.call(
            "/api/referrals/link", {"referralCode": self.code(self.t)})[0])
        self.assertEqual(409, self.teacher.call(
            "/api/referrals/link", {"referralCode": self.code(self.l)})[0])
        self.assertEqual(403, self.admin.call(
            "/api/referrals/link", {"referralCode": self.code(self.t)})[0])
        self.assertFalse(self.status(self.teacher)[1]["linked"])

    def test_revoked_inviter_keeps_history_but_no_new_link(self):
        self.assertEqual(200, self.learner.call(
            "/api/referrals/link", {"referralCode": self.code(self.o)})[0])
        with server.connect() as db:
            db.execute("UPDATE users SET role='admin' WHERE id=?", (self.o["id"],))
        self.assertTrue(self.status(self.learner)[1]["linked"])
        self.assertEqual(400, self.teacher.call(
            "/api/referrals/link", {"referralCode": self.code(self.o)})[0])

    def test_static_pages_are_reachable_and_signup_prefill_wired(self):
        for path, expected in (
            ("/phase3/referral-center.html", "소개 관계 확인"),
            ("/phase3/referral-compliance-review.html", "법률"),
        ):
            with self.subTest(path=path):
                connection = http.client.HTTPConnection("127.0.0.1", self.http.server_port)
                connection.request("GET", path)
                response = connection.getresponse()
                body = response.read().decode("utf-8")
                self.assertEqual(200, response.status, body[:200])
                self.assertIn(expected, body)
                connection.close()
        with open(server.ROOT / "app.js", encoding="utf-8") as f:
            self.assertIn("const invited=new URLSearchParams(location.search).get('ref')", f.read())
        with open(server.ROOT / "shell.html", encoding="utf-8") as f:
            self.assertIn('href="/phase3/referral-center.html"', f.read())


if __name__ == "__main__":
    unittest.main()
