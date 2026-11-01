"""#109: trusted SQLite evidence integration regressions (test DB only)."""
import sqlite3
import unittest
from pathlib import Path

from team14_persistent import SimError
from team14_referral_risk_db_adapter import screen_phase3_referral_evidence


class Task109TrustedEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript(Path(__file__).with_name("schema.sql").read_text())
        for user_id, role in (("child", "learner"), ("parent", "learner"),
                              ("teacher", "teacher"), ("other", "learner")):
            self.db.execute(
                "INSERT INTO users(id,email,password,nickname,role,referral_code,created_at)"
                " VALUES(?,?,?,?,?,?,?)",
                (user_id, user_id + "@example.test", "test", user_id,
                 role, "code_" + user_id, 100.0),
            )
        self.db.execute(
            "INSERT INTO slots(id,teacher_id,start,end) VALUES(?,?,?,?)",
            ("slot1", "teacher", 1000.0, 2000.0),
        )
        self.db.execute(
            "INSERT INTO bookings(id,learner_id,teacher_id,slot_id,unit_id,status,"
            "price,referrer_id,room,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            ("booking1", "child", "teacher", "slot1", "unit1", "completed",
             20000, "parent", "room1", 100.0),
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def check(self, **changes):
        args = dict(referred_id="child", inviter_id="parent",
                    booking_id="booking1")
        args.update(changes)
        return screen_phase3_referral_evidence(self.db, **args)

    def add_test_charge(self, *, amount=20000, beneficiary="child", created_at=110.0):
        self.db.execute(
            "INSERT INTO ledger(booking_id,kind,amount,beneficiary,created_at)"
            " VALUES(?,?,?,?,?)",
            ("booking1", "test_charge", amount, beneficiary, created_at),
        )

    def add_provider_event(self, *, session_at=110.0, event_at=111.0):
        self.db.execute(
            "INSERT INTO payment_sessions(booking_id,session_id,url,created_at)"
            " VALUES(?,?,?,?)",
            ("booking1", "session1", "https://example.test/checkout", session_at),
        )
        self.db.execute(
            "INSERT INTO provider_events(event_id,session_id,booking_id,created_at)"
            " VALUES(?,?,?,?)",
            ("event1", "session1", "booking1", event_at),
        )

    def add_attendance(self):
        for uid in ("child", "teacher"):
            self.db.execute(
                "INSERT INTO attendance(booking_id,user_id,joined,last_seen,seconds,confirmed)"
                " VALUES(?,?,?,?,?,?)",
                ("booking1", uid, 120.0, 160.0, 40.0, 1),
            )

    def test_01_missing_provider_and_charge_fail_closed(self):
        result = self.check()
        self.assertIn("TRANSACTION_EVIDENCE_MISSING", result["flags"])
        self.assertIn("PROVIDER_TEST_EVIDENCE_MISSING", result["flags"])

    def test_02_charge_without_provider_event_is_not_verified(self):
        self.add_test_charge()
        self.assertIn("TRANSACTION_EVIDENCE_MISSING", self.check()["flags"])

    def test_03_provider_event_without_charge_is_not_verified(self):
        self.add_provider_event()
        self.assertIn("TRANSACTION_EVIDENCE_MISSING", self.check()["flags"])
        self.assertNotIn("PROVIDER_TEST_EVIDENCE_MISSING", self.check()["flags"])

    def test_04_completed_booking_without_attendance_fails_closed(self):
        self.add_provider_event()
        self.add_test_charge()
        self.assertIn("TRANSACTION_EVIDENCE_MISSING", self.check()["flags"])

    def test_05_full_test_evidence_is_still_review_only(self):
        self.add_provider_event()
        self.add_test_charge()
        self.add_attendance()
        result = self.check()
        self.assertNotIn("TRANSACTION_EVIDENCE_MISSING", result["flags"])
        self.assertIn("MULTI_ACCOUNT_IDENTITY_UNVERIFIED", result["flags"])
        self.assertTrue(result["review_required"])
        self.assertFalse(result["account_identity_assessed"])
        self.assertEqual("REVIEW_ONLY", result["decision"])
        self.assertFalse(result["source_verified_for_production"])
        self.assertFalse(result["actual_payment_verified"])
        for flag in ("real_money", "payment_enabled", "reward_authorized",
                     "policy_approved"):
            self.assertIs(result[flag], False)

    def test_06_db_immutable_parent_conflict(self):
        self.db.execute("UPDATE users SET referred_by='other' WHERE id='child'")
        self.assertIn("IMMUTABLE_PARENT_CONFLICT", self.check()["flags"])

    def test_07_db_reciprocal_cycle_detected(self):
        self.db.execute("UPDATE users SET referred_by='child' WHERE id='parent'")
        self.assertIn("CYCLE_OR_RECIPROCAL", self.check()["flags"])

    def test_08_booking_referrer_mismatch_detected(self):
        self.db.execute("UPDATE bookings SET referrer_id='other' WHERE id='booking1'")
        self.assertIn("BOOKING_REFERRER_MISMATCH", self.check()["flags"])

    def test_09_booking_owner_mismatch_detected(self):
        self.db.execute("UPDATE bookings SET learner_id='other' WHERE id='booking1'")
        self.assertIn("BOOKING_OWNER_MISMATCH", self.check()["flags"])

    def test_10_no_booking_is_unknown_not_clean(self):
        result = self.check(booking_id=None)
        self.assertIn("TRANSACTION_NOT_ASSESSED", result["flags"])
        self.assertIn("MULTI_ACCOUNT_IDENTITY_UNVERIFIED", result["flags"])

    def test_11_missing_account_or_booking_fails_closed(self):
        for changes in (dict(referred_id="absent"),
                        dict(inviter_id="absent"),
                        dict(booking_id="absent")):
            with self.subTest(changes=changes), self.assertRaises(SimError):
                self.check(**changes)

    def test_12_reject_client_like_connection_and_identifiers(self):
        for bad in (None, {}, "connection"):
            with self.subTest(bad=bad), self.assertRaises(SimError):
                screen_phase3_referral_evidence(
                    bad, referred_id="child", inviter_id="parent")
        for bad in ("../child", "", 5, True):
            with self.subTest(bad=bad), self.assertRaises(SimError):
                self.check(referred_id=bad)

    def test_13_read_only_even_with_complete_evidence(self):
        self.add_provider_event()
        self.add_test_charge()
        self.add_attendance()
        before = self.db.total_changes
        self.db.execute("PRAGMA query_only=ON")
        result = self.check()
        self.assertEqual(before, self.db.total_changes)
        self.assertEqual("REVIEW_ONLY", result["decision"])

    def test_14_missing_confirmation_does_not_pass(self):
        self.add_provider_event()
        self.add_test_charge()
        self.add_attendance()
        self.db.execute(
            "UPDATE attendance SET confirmed=0 WHERE user_id='teacher'")
        self.assertIn("TRANSACTION_EVIDENCE_MISSING", self.check()["flags"])

    def test_15_uncompleted_booking_does_not_pass(self):
        self.add_provider_event()
        self.add_test_charge()
        self.add_attendance()
        self.db.execute("UPDATE bookings SET status='test_paid' WHERE id='booking1'")
        self.assertIn("TRANSACTION_EVIDENCE_MISSING", self.check()["flags"])


    def _assert_invalid_charge(self, **kwargs):
        self.add_provider_event()
        self.add_test_charge(**kwargs)
        self.add_attendance()
        result = self.check()
        self.assertIn("TRANSACTION_EVIDENCE_MISSING", result["flags"])
        self.assertIn("TEST_CHARGE_EVIDENCE_INVALID", result["flags"])
        self.assertEqual("REVIEW_ONLY", result["decision"])

    def test_16_reject_charge_price_mismatch(self):
        self._assert_invalid_charge(amount=1)

    def test_17_reject_wrong_charge_beneficiary(self):
        self._assert_invalid_charge(beneficiary="other")

    def test_18_reject_negative_charge(self):
        self._assert_invalid_charge(amount=-20000)

    def test_19_reject_zero_charge(self):
        self._assert_invalid_charge(amount=0)

    def test_20_reject_provider_event_before_session(self):
        self.add_provider_event(event_at=109.0)
        self.add_test_charge()
        self.add_attendance()
        result = self.check()
        self.assertIn("TRANSACTION_EVIDENCE_MISSING", result["flags"])
        self.assertIn("PROVIDER_TEST_EVIDENCE_MISSING", result["flags"])

    def test_21_reject_session_before_booking(self):
        self.add_provider_event(session_at=90.0, event_at=111.0)
        self.add_test_charge()
        self.add_attendance()
        self.assertIn("TRANSACTION_EVIDENCE_MISSING", self.check()["flags"])

    def test_22_reject_charge_before_booking(self):
        self._assert_invalid_charge(created_at=90.0)

    def test_23_reject_conflicting_second_provider_event(self):
        self.add_provider_event()
        self.db.execute(
            "INSERT INTO provider_events(event_id,session_id,booking_id,created_at)"
            " VALUES(?,?,?,?)", ("event2", "session1", "booking1", 109.0)
        )
        self.add_test_charge()
        self.add_attendance()
        self.assertIn("TRANSACTION_EVIDENCE_MISSING", self.check()["flags"])


if __name__ == "__main__":
    unittest.main()
