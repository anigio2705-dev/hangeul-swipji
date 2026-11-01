"""A regression tests for #123 signed simulator + isolated atomic SQLite.

No real provider keys, live DB, payment network, or operating API.
"""
import hashlib
import hmac
import json
import os
import sqlite3
import tempfile
import unittest

from team14_payment_booking_signed_store import (
    apply_test_signed_event, initialize_review_db, read_review_snapshot,
    seed_review_booking,
)

KEY = b"isolated-local-test-key-32-bytes-only-never-prod"


def make_event(outcome="SUCCESS", *, event_id="event_1", sequence=1,
               payment_id="payment_1", booking_id="booking_1",
               source="TEST_SIGNED_PROVIDER_SIMULATOR"):
    return {"source": source, "booking_id": booking_id, "payment_id": payment_id,
            "event_id": event_id, "sequence": sequence, "outcome": outcome}


def signed(event, key=KEY):
    payload = json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = "sha256=" + hmac.new(key, payload, hashlib.sha256).hexdigest()
    return dict(payload=payload, signature=signature, test_key=key)


class SignedSimulatorSqliteTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        initialize_review_db(self.db)
        seed_review_booking(self.db, booking_id="booking_1", payment_id="payment_1",
                            lesson_count=4, completed_lessons=1)

    def tearDown(self):
        self.db.close()

    def apply(self, event=None, **kwargs):
        return apply_test_signed_event(
            self.db, **signed(make_event() if event is None else event), **kwargs)

    def assert_isolated(self, result):
        self.assertEqual("SIGNED_SIMULATOR_SQLITE_REVIEW_ONLY", result["status"])
        self.assertTrue(result["simulator_signature_checked"])
        self.assertTrue(result["atomic_review_db_update"])
        for key in ("payment_event_provenance_verified", "operating_db_connected",
                    "production_booking_updated", "real_money_enabled",
                    "provider_api_called", "authenticated_user_api_connected"):
            self.assertIs(result[key], False, key)

    def test_signed_success_persists_booking_and_remaining_lessons(self):
        r = self.apply()
        self.assertEqual(("PAID", "ACTIVE", 3, 1),
                         tuple(r["snapshot"][k] for k in (
                             "payment_state", "booking_state",
                             "remaining_bookable_lessons", "version")))
        self.assertEqual(1, r["snapshot"]["completed_lessons"])
        self.assert_isolated(r)

    def test_exact_replay_is_idempotent(self):
        a = self.apply()
        b = self.apply()
        self.assertFalse(a["idempotent_replay"])
        self.assertTrue(b["idempotent_replay"])
        self.assertEqual(1, b["snapshot"]["version"])
        self.assertEqual(1, self.db.execute(
            "SELECT COUNT(*) FROM review_payment_events").fetchone()[0])

    def test_wrong_hmac_is_rejected_without_db_write(self):
        p = signed(make_event())
        p["signature"] = "sha256=" + "0" * 64
        with self.assertRaises(ValueError):
            apply_test_signed_event(self.db, **p)
        self.assertEqual(0, read_review_snapshot(
            self.db, booking_id="booking_1")["version"])

    def test_malformed_header_and_weak_key_rejected(self):
        for signature in ("", "sha256=xyz", "sha256=" + "A" * 64):
            with self.subTest(signature=signature), self.assertRaises(ValueError):
                apply_test_signed_event(self.db, payload=b"{}", signature=signature,
                                        test_key=KEY)
        with self.assertRaises(ValueError):
            apply_test_signed_event(self.db, **signed(make_event(), key=b"short"))

    def test_cross_payment_and_unknown_booking_fail_closed(self):
        for changed in ({"payment_id": "payment_2"}, {"booking_id": "booking_2"}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.apply(make_event(**changed))
        self.assertEqual(0, self.db.execute(
            "SELECT COUNT(*) FROM review_payment_events").fetchone()[0])

    def test_conflicting_event_id_replay_rolls_back(self):
        self.apply()
        with self.assertRaises(ValueError):
            self.apply(make_event(outcome="CANCELED"))
        self.assertEqual(1, read_review_snapshot(
            self.db, booking_id="booking_1")["version"])

    def test_conflicting_sequence_rolls_back(self):
        self.apply()
        with self.assertRaises(ValueError):
            self.apply(make_event("CANCELED", event_id="event_2", sequence=1))
        self.assertEqual(1, self.db.execute(
            "SELECT COUNT(*) FROM review_payment_events").fetchone()[0])

    def test_out_of_order_cancel_after_success_requires_review(self):
        self.apply(make_event("CANCELED", event_id="event_2", sequence=2))
        r = self.apply(make_event("SUCCESS", event_id="event_1", sequence=1))
        self.assertEqual("REVIEW_REQUIRED", r["snapshot"]["booking_state"])
        self.assertEqual(0, r["snapshot"]["remaining_bookable_lessons"])
        self.assertEqual(1, r["snapshot"]["completed_lessons"])

    def test_source_spoof_and_extra_field_rejected(self):
        for bad in (make_event(source="REAL_GATEWAY"),
                    dict(make_event(), live_payment=True)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.apply(bad)
        self.assertEqual(0, read_review_snapshot(
            self.db, booking_id="booking_1")["version"])

    def test_duplicate_json_keys_rejected(self):
        raw = (b'{"source":"TEST_SIGNED_PROVIDER_SIMULATOR",'
               b'"booking_id":"booking_1","payment_id":"payment_1",'
               b'"event_id":"event_1","sequence":1,"outcome":"SUCCESS",'
               b'"outcome":"CANCELED"}')
        sig = "sha256=" + hmac.new(KEY, raw, hashlib.sha256).hexdigest()
        with self.assertRaises(ValueError):
            apply_test_signed_event(self.db, payload=raw, signature=sig, test_key=KEY)

    def test_failure_timeout_cancel_never_unlock_lesson(self):
        for outcome in ("FAILURE", "TIMEOUT", "CANCELED"):
            with self.subTest(outcome=outcome):
                c = sqlite3.connect(":memory:")
                try:
                    initialize_review_db(c)
                    seed_review_booking(c, booking_id="booking_1", payment_id="payment_1",
                                        lesson_count=4, completed_lessons=0)
                    r = apply_test_signed_event(c, **signed(make_event(outcome)))
                    self.assertEqual(0, r["snapshot"]["remaining_bookable_lessons"])
                finally:
                    c.close()

    def test_completed_lessons_preserved_after_cancellation(self):
        self.apply()
        r = self.apply(make_event("CANCELED", event_id="event_2", sequence=2))
        self.assertEqual(1, r["snapshot"]["completed_lessons"])
        self.assertEqual("REVIEW_REQUIRED", r["snapshot"]["booking_state"])
        self.assertEqual(0, r["snapshot"]["remaining_bookable_lessons"])

    def test_file_backed_test_db_survives_reopen(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "isolated-review.sqlite")
            c = sqlite3.connect(path)
            try:
                initialize_review_db(c)
                seed_review_booking(c, booking_id="booking_1", payment_id="payment_1",
                                    lesson_count=4)
                apply_test_signed_event(c, **signed(make_event()))
            finally:
                c.close()
            c = sqlite3.connect(path)
            try:
                row = read_review_snapshot(c, booking_id="booking_1")
                self.assertEqual(("PAID", 4, 1),
                                 (row["payment_state"], row["remaining_bookable_lessons"],
                                  row["version"]))
            finally:
                c.close()

    def test_invalid_projection_event_rolls_back_transaction(self):
        with self.assertRaises(ValueError):
            self.apply(make_event("UNSUPPORTED"))
        self.assertEqual(0, self.db.execute(
            "SELECT COUNT(*) FROM review_payment_events").fetchone()[0])
        self.assertEqual(0, read_review_snapshot(
            self.db, booking_id="booking_1")["version"])


if __name__ == "__main__":
    unittest.main()
