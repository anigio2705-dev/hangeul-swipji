"""B/15 independent #109 trusted-evidence QA; exact A SHA f2e18f3733ea8defa1ddbe965944d17b92719280.

Independent negative controls on LOCAL TEST SQLite only. No product edits,
production data, real payment, deployment, or policy authorization.
"""
import sqlite3
import unittest
from pathlib import Path

from team14_referral_risk_db_adapter import screen_phase3_referral_evidence


class BQA109TrustedEvidence(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript(Path(__file__).with_name("schema.sql").read_text())
        for uid, role in (("student", "learner"), ("referrer", "learner"),
                          ("tutor", "teacher"), ("outsider", "learner")):
            self.db.execute(
                "INSERT INTO users(id,email,password,nickname,role,referral_code,created_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (uid, uid + "@example.test", "fixture", uid, role, "ref_" + uid, 100.0))
        self.db.execute(
            "INSERT INTO slots(id,teacher_id,start,end) VALUES(?,?,?,?)",
            ("s1", "tutor", 1000.0, 2000.0))
        self.db.execute(
            "INSERT INTO bookings(id,learner_id,teacher_id,slot_id,unit_id,status,"
            "price,referrer_id,room,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            ("b1", "student", "tutor", "s1", "u1", "completed", 20000,
             "referrer", "room1", 100.0))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def add_provider(self, *, event_time=120.0):
        self.db.execute(
            "INSERT INTO payment_sessions(booking_id,session_id,url,created_at) "
            "VALUES(?,?,?,?)", ("b1", "sess1", "https://example.test/pay", 110.0))
        self.db.execute(
            "INSERT INTO provider_events(event_id,session_id,booking_id,created_at) "
            "VALUES(?,?,?,?)", ("ev1", "sess1", "b1", event_time))

    def add_charge(self, *, amount=20000, beneficiary="student"):
        self.db.execute(
            "INSERT INTO ledger(booking_id,kind,amount,beneficiary,created_at) "
            "VALUES(?,?,?,?,?)", ("b1", "test_charge", amount, beneficiary, 115.0))

    def add_attendance(self, *, student_confirmed=1, tutor_confirmed=1):
        for uid, confirmed in (("student", student_confirmed),
                               ("tutor", tutor_confirmed)):
            self.db.execute(
                "INSERT INTO attendance(booking_id,user_id,joined,last_seen,seconds,confirmed) "
                "VALUES(?,?,?,?,?,?)", ("b1", uid, 150.0, 170.0, 20.0, confirmed))

    def screen(self, booking_id="b1", **kwargs):
        args = dict(referred_id="student", inviter_id="referrer", booking_id=booking_id)
        args.update(kwargs)
        return screen_phase3_referral_evidence(self.db, **args)

    def complete(self):
        self.add_provider()
        self.add_charge()
        self.add_attendance()

    def assert_review_only(self, r):
        self.assertEqual("REVIEW_ONLY", r["decision"])
        self.assertIs(r["review_required"], True)
        self.assertIn("MULTI_ACCOUNT_IDENTITY_UNVERIFIED", r["flags"])
        for k in ("real_money", "payment_enabled", "reward_authorized",
                  "policy_approved", "actual_payment_verified",
                  "source_verified_for_production", "account_identity_assessed"):
            self.assertIs(r[k], False, k)

    def assert_untrusted(self):
        r = self.screen()
        self.assertIn("TRANSACTION_EVIDENCE_MISSING", r["flags"])
        self.assert_review_only(r)

    def test_01_consistent_fixture_is_review_only(self):
        self.complete()
        r = self.screen()
        self.assertNotIn("TRANSACTION_EVIDENCE_MISSING", r["flags"])
        self.assert_review_only(r)

    def test_02_charge_amount_must_equal_booking_price(self):
        self.add_provider()
        self.add_charge(amount=1)  # real booking price is 20000
        self.add_attendance()
        self.assert_untrusted()

    def test_03_charge_beneficiary_must_match_booking_owner(self):
        self.add_provider()
        self.add_charge(beneficiary="outsider")
        self.add_attendance()
        self.assert_untrusted()

    def test_04_negative_charge_must_not_verify_transaction(self):
        self.add_provider()
        self.add_charge(amount=-20000)
        self.add_attendance()
        self.assert_untrusted()

    def test_05_zero_charge_must_not_verify_transaction(self):
        self.add_provider()
        self.add_charge(amount=0)
        self.add_attendance()
        self.assert_untrusted()

    def test_06_provider_event_before_session_is_not_valid_evidence(self):
        self.add_provider(event_time=109.0)  # session created at 110
        self.add_charge()
        self.add_attendance()
        self.assert_untrusted()

    def test_07_no_provider_event_is_not_verified(self):
        self.add_charge()
        self.add_attendance()
        self.assert_untrusted()

    def test_08_unconfirmed_tutor_is_not_verified(self):
        self.add_provider()
        self.add_charge()
        self.add_attendance(tutor_confirmed=0)
        self.assert_untrusted()

    def test_09_referrer_mismatch_and_identity_unknown(self):
        self.complete()
        self.db.execute("UPDATE bookings SET referrer_id='outsider' WHERE id='b1'")
        r = self.screen()
        self.assertIn("BOOKING_REFERRER_MISMATCH", r["flags"])
        self.assert_review_only(r)

    def test_10_no_booking_cannot_clear_transaction(self):
        r = self.screen(booking_id=None)
        self.assertIn("TRANSACTION_NOT_ASSESSED", r["flags"])
        self.assert_review_only(r)

    def test_11_complete_fixture_read_only_sqlite(self):
        self.complete()
        prior = self.db.total_changes
        self.db.execute("PRAGMA query_only=ON")
        self.assert_review_only(self.screen())
        self.assertEqual(prior, self.db.total_changes)


if __name__ == "__main__":
    unittest.main()
