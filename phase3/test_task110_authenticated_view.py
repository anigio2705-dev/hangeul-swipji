"""#110 local-session participant explanation: auth, DB and no-money regressions."""
import hashlib
import sqlite3
import unittest
from pathlib import Path

from team14_referral_authenticated_view import authenticated_local_referral_view
from team14_referral_participant_view import render_participant_html


class AuthenticatedParticipantViewTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript(Path(__file__).with_name("schema.sql").read_text())
        for uid, role, approved in (
            ("student", "learner", 0), ("tutor", "teacher", 1),
            ("inviter", "learner", 0), ("operator", "admin", 1),
            ("outsider", "learner", 0),
        ):
            self.db.execute(
                "INSERT INTO users(id,email,password,nickname,role,approved,"
                "referral_code,referred_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (uid, uid + "@example.test", "test", uid, role, approved,
                 "code_" + uid, None, 100),
            )
            token = self.token(uid)
            self.db.execute(
                "INSERT INTO sessions(token,user_id,expires) VALUES(?,?,?)",
                (hashlib.sha256(token.encode()).hexdigest(), uid, 10000),
            )
        # Seed FK parents first; attach the learner referral after all users exist.
        self.db.execute("UPDATE users SET referred_by=? WHERE id=?",
                        ("inviter", "student"))
        self.db.execute(
            "INSERT INTO slots(id,teacher_id,start,end) VALUES(?,?,?,?)",
            ("slot1", "tutor", 2000, 3000),
        )
        self.db.execute(
            "INSERT INTO bookings(id,learner_id,teacher_id,slot_id,unit_id,"
            "status,price,referrer_id,room,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            ("booking1", "student", "tutor", "slot1", "unit1", "completed",
             20000, "inviter", "room1", 100),
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()

    @staticmethod
    def token(uid):
        return "fixture_" + uid + "_token"

    def view(self, uid="student", **changes):
        params = dict(session_token=self.token(uid), booking_id="booking1",
                      now=1000)
        params.update(changes)
        return authenticated_local_referral_view(self.db, **params)

    def test_01_all_four_real_session_roles_are_distinct(self):
        for uid, role in (("student", "learner"), ("tutor", "teacher"),
                          ("inviter", "referrer"), ("operator", "platform")):
            with self.subTest(uid=uid):
                result = self.view(uid)
                self.assertEqual(role, result["role"])
                self.assertTrue(result["session_authenticated"])
                self.assertEqual("POLICY_UNVERIFIED", result["state"])

    def test_02_nonparticipant_session_denied(self):
        with self.assertRaises(PermissionError):
            self.view("outsider")

    def test_03_missing_and_expired_sessions_denied(self):
        for token in ("fixture_missing_token", self.token("student") + "x"):
            with self.subTest(token=token), self.assertRaises(PermissionError):
                self.view(session_token=token)
        with self.assertRaises(PermissionError):
            self.view(now=10000)

    def test_04_no_browser_actor_or_roster_override(self):
        with self.assertRaises(TypeError):
            self.view("outsider", role="referrer")
        with self.assertRaises(TypeError):
            self.view("outsider", authenticated_actor_id="student")

    def test_05_unknown_booking_not_enumerable(self):
        with self.assertRaises(PermissionError):
            self.view(booking_id="not_found")

    def test_06_bad_identifier_and_sql_injection_rejected(self):
        for bad in ("../booking1", "booking1' OR 1=1 --", "", 123, True):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.view(booking_id=bad)

    def test_07_referral_relationship_mismatch_fails_closed(self):
        self.db.execute("UPDATE users SET referred_by='outsider' WHERE id='student'")
        with self.assertRaises(PermissionError):
            self.view("inviter")

    def test_08_booking_referrer_forgery_fails_closed(self):
        self.db.execute("UPDATE bookings SET referrer_id='outsider' WHERE id='booking1'")
        with self.assertRaises(PermissionError):
            self.view("student")

    def test_09_self_referral_or_teacher_referral_fails_closed(self):
        for uid in ("student", "tutor"):
            self.db.execute("UPDATE bookings SET referrer_id=? WHERE id='booking1'", (uid,))
            with self.subTest(uid=uid), self.assertRaises(PermissionError):
                self.view()

    def test_10_teacher_approval_revocation_applies_immediately(self):
        self.db.execute("UPDATE users SET approved=0 WHERE id='tutor'")
        with self.assertRaises(PermissionError):
            self.view("tutor")

    def test_11_actor_role_revocation_applies_immediately(self):
        self.db.execute("UPDATE users SET role='learner' WHERE id='tutor'")
        with self.assertRaises(PermissionError):
            self.view("tutor")

    def test_12_referrer_without_link_is_never_invented(self):
        self.db.execute("UPDATE bookings SET referrer_id=NULL WHERE id='booking1'")
        result = self.view("student")
        self.assertEqual("POLICY_UNVERIFIED", result["state"])
        with self.assertRaises(PermissionError):
            self.view("inviter")

    def test_13_no_signed_fixture_can_activate_payment(self):
        for uid in ("student", "tutor", "inviter", "operator"):
            v = self.view(uid)
            self.assertIsNone(v["hypothetical_candidate_krw"])
            self.assertFalse(v["business_policy_approved"])
            self.assertFalse(v["provider_payment_verified"])
            self.assertFalse(v["production_policy_activated"])
            self.assertFalse(v["live_payment_enabled"])
            self.assertFalse(v["live_payout_enabled"])
            self.assertFalse(v["original_contract_ready"])

    def test_14_query_only_db_and_no_mutation(self):
        before = self.db.total_changes
        self.db.execute("PRAGMA query_only=ON")
        self.view("inviter")
        self.assertEqual(before, self.db.total_changes)

    def test_15_invalid_clock_and_session_token(self):
        for clock in (True, -1, float("nan"), float("inf"), 4102444801):
            with self.subTest(clock=clock), self.assertRaises(ValueError):
                self.view(now=clock)
        for token in ("x", "../token", None, True, "a" * 257):
            with self.subTest(token=token), self.assertRaises(PermissionError):
                self.view(session_token=token)

    def test_16_malformed_booking_state_or_price_fails_closed(self):
        self.db.execute("UPDATE bookings SET status='forged' WHERE id='booking1'")
        with self.assertRaises(PermissionError):
            self.view()
        self.db.execute("UPDATE bookings SET status='completed',price=-1 WHERE id='booking1'")
        with self.assertRaises(PermissionError):
            self.view()

    def test_17_html_remains_static_csp_no_money(self):
        for uid in ("student", "tutor", "inviter", "operator"):
            html = render_participant_html(self.view(uid))
            self.assertIn("Content-Security-Policy", html)
            self.assertNotIn("<form", html)
            self.assertNotIn("fetch(", html)
            self.assertNotIn("가상 후보 금액:", html)

    def test_18_no_client_dict_or_fake_db(self):
        with self.assertRaises(ValueError):
            authenticated_local_referral_view(
                {}, session_token=self.token("student"),
                booking_id="booking1", now=1000)


    def test_19_booking_teacher_must_match_slot_owner(self):
        self.db.execute(
            "INSERT INTO users(id,email,password,nickname,role,approved,"
            "referral_code,created_at) VALUES(?,?,?,?,?,?,?,?)",
            ("tutor2", "tutor2@example.test", "test", "tutor2", "teacher",
             1, "code_tutor2", 100),
        )
        token = self.token("tutor2")
        self.db.execute(
            "INSERT INTO sessions(token,user_id,expires) VALUES(?,?,?)",
            (hashlib.sha256(token.encode()).hexdigest(), "tutor2", 10000),
        )
        self.db.execute(
            "UPDATE bookings SET teacher_id=? WHERE id=?",
            ("tutor2", "booking1"),
        )
        with self.assertRaises(PermissionError):
            self.view("tutor2")
        with self.assertRaises(PermissionError):
            self.view("student")

    def test_20_changed_slot_owner_never_authorizes_participant(self):
        self.db.execute("UPDATE slots SET teacher_id=? WHERE id=?",
                        ("outsider", "slot1"))
        with self.assertRaises(PermissionError):
            self.view("student")


if __name__ == "__main__":
    unittest.main()
