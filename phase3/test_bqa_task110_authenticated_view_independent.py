"""B/15 independent QA-only #110 local session/booking view, exact product SHA 2e0494f5.

Independent negative controls; local in-memory SQLite only. No product writes.
"""
import hashlib
import sqlite3
import unittest
from pathlib import Path

from team14_referral_authenticated_view import authenticated_local_referral_view
from team14_referral_participant_view import render_participant_html


class BQA110SessionBooking(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript(Path(__file__).with_name("schema.sql").read_text())
        for uid, role, approved, parent in (
            ("refer1", "learner", 0, None),
            ("teacher1", "teacher", 1, None),
            ("teacher2", "teacher", 1, None),
            ("learner1", "learner", 0, "refer1"),
            ("admin1", "admin", 1, None),
            ("visitor", "learner", 0, None),
        ):
            self.db.execute(
                "INSERT INTO users(id,email,password,nickname,role,approved,"
                "referral_code,referred_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (uid, uid + "@example.test", "test", uid, role, approved,
                 "code_" + uid, parent, 100.0))
            self.db.execute(
                "INSERT INTO sessions(token,user_id,expires) VALUES(?,?,?)",
                (hashlib.sha256(self.token(uid).encode("ascii")).hexdigest(), uid, 5000))
        self.db.execute("INSERT INTO slots(id,teacher_id,start,end) VALUES(?,?,?,?)",
                        ("slot1", "teacher1", 1000, 2000))
        self.db.execute(
            "INSERT INTO bookings(id,learner_id,teacher_id,slot_id,unit_id,status,"
            "price,referrer_id,room,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            ("booking1", "learner1", "teacher1", "slot1", "unit1", "completed",
             25000, "refer1", "room1", 100))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    @staticmethod
    def token(uid):
        return "bqa_fixture_" + uid + "_session"

    def view(self, uid="learner1", **overrides):
        kw = dict(session_token=self.token(uid), booking_id="booking1", now=1500)
        kw.update(overrides)
        return authenticated_local_referral_view(self.db, **kw)

    def assert_never_live(self, result):
        self.assertEqual("POLICY_UNVERIFIED", result["state"])
        self.assertIsNone(result["hypothetical_candidate_krw"])
        for key in ("provider_payment_verified", "business_policy_approved",
                    "production_session_verified", "original_contract_ready",
                    "live_payment_enabled", "live_payout_enabled"):
            self.assertIs(result[key], False, key)

    def test_01_four_distinct_server_derived_roles(self):
        for uid, role in (("learner1", "learner"), ("teacher1", "teacher"),
                          ("refer1", "referrer"), ("admin1", "platform")):
            with self.subTest(uid=uid):
                result = self.view(uid)
                self.assertEqual(role, result["role"])
                self.assert_never_live(result)

    def test_02_outsider_and_unrelated_teacher_denied(self):
        for uid in ("visitor", "teacher2"):
            with self.subTest(uid=uid), self.assertRaises(PermissionError):
                self.view(uid)

    def test_03_session_hash_not_plaintext_token(self):
        self.db.execute("UPDATE sessions SET token=? WHERE user_id='learner1'",
                        (self.token("learner1"),))
        with self.assertRaises(PermissionError):
            self.view()

    def test_04_revoked_and_expired_session_denied(self):
        self.db.execute("DELETE FROM sessions WHERE user_id='refer1'")
        with self.assertRaises(PermissionError):
            self.view("refer1")
        with self.assertRaises(PermissionError):
            self.view("learner1", now=5000)

    def test_05_role_demoted_teacher_denied(self):
        self.db.execute("UPDATE users SET role='learner' WHERE id='teacher1'")
        with self.assertRaises(PermissionError):
            self.view("teacher1")

    def test_06_unapproved_teacher_denied(self):
        self.db.execute("UPDATE users SET approved=0 WHERE id='teacher1'")
        with self.assertRaises(PermissionError):
            self.view("teacher1")

    def test_07_referral_link_disagreement_denied(self):
        self.db.execute("UPDATE users SET referred_by='visitor' WHERE id='learner1'")
        with self.assertRaises(PermissionError):
            self.view("refer1")

    def test_08_booking_referrer_self_reference_denied(self):
        self.db.execute("UPDATE bookings SET referrer_id='learner1' WHERE id='booking1'")
        with self.assertRaises(PermissionError):
            self.view()

    def test_09_invalid_booking_price_and_status_denied(self):
        self.db.execute("UPDATE bookings SET price=-100 WHERE id='booking1'")
        with self.assertRaises(PermissionError):
            self.view()
        self.db.execute("UPDATE bookings SET price=25000,status='paid_live' WHERE id='booking1'")
        with self.assertRaises(PermissionError):
            self.view()

    def test_10_unknown_booking_hidden_from_participant(self):
        with self.assertRaises(PermissionError):
            self.view(booking_id="booking_missing")

    def test_11_reject_caller_role_or_payment_evidence(self):
        for key, val in (("authenticated_actor_id", "admin1"),
                         ("payment_verified", True),
                         ("trusted_roster", {"platform": "visitor"})):
            with self.subTest(key=key), self.assertRaises(TypeError):
                self.view("visitor", **{key: val})

    def test_12_invalid_session_token_and_booking_identifier(self):
        with self.assertRaises(PermissionError):
            self.view(session_token="../etc/passwd")
        with self.assertRaises(ValueError):
            self.view(booking_id="booking1' OR 1=1")

    def test_13_html_csp_and_no_money_for_every_role(self):
        for uid in ("learner1", "teacher1", "refer1", "admin1"):
            html = render_participant_html(self.view(uid))
            self.assertIn("Content-Security-Policy", html)
            self.assertNotIn("<form", html)
            self.assertNotIn("fetch(", html)

    def test_14_query_only_and_no_side_effects(self):
        before = self.db.total_changes
        self.db.execute("PRAGMA query_only=ON")
        self.assert_never_live(self.view("refer1"))
        self.assertEqual(before, self.db.total_changes)

    def test_15_slot_teacher_and_booking_teacher_must_agree(self):
        """Contradictory trusted DB rows must not authorize a different teacher."""
        self.db.execute("UPDATE bookings SET teacher_id='teacher2' WHERE id='booking1'")
        with self.assertRaises(PermissionError):
            self.view("teacher2")


if __name__ == "__main__":
    unittest.main()
