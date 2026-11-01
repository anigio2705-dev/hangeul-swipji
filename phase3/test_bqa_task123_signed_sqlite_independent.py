"""B/15 independent adversarial QA for exact A #123 repaired signed SQLite simulator SHA a8426d0.

Review-only tests. No provider credentials, production DB, money, or network.
Tests intentionally require malformed JSON types to fail as ValueError BEFORE
SQLite parameter binding; failures are actionable input-validation findings.
"""
import hashlib
import hmac
import json
import os
import sqlite3
import tempfile
import unittest

from team14_payment_booking_signed_store import (
    initialize_review_db, seed_review_booking, apply_test_signed_event,
    read_review_snapshot,
)

TEST_KEY = b"b-independent-test-key-material-32-bytes-only"


def event(**changes):
    data = dict(source="TEST_SIGNED_PROVIDER_SIMULATOR",
                booking_id="booking_1", payment_id="payment_1",
                event_id="evt_1", sequence=1, outcome="SUCCESS")
    data.update(changes)
    return data


def signed(data, *, key=TEST_KEY):
    payload = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    return dict(payload=payload,
                signature="sha256=" + hmac.new(key, payload, hashlib.sha256).hexdigest(),
                test_key=key)


class IndependentSignedSqliteReview(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        initialize_review_db(self.db)
        seed_review_booking(self.db, booking_id="booking_1", payment_id="payment_1",
                            lesson_count=5, completed_lessons=2)

    def tearDown(self):
        self.db.close()

    def send(self, **changes):
        return apply_test_signed_event(self.db, **signed(event(**changes)))

    def snapshot(self):
        return read_review_snapshot(self.db, booking_id="booking_1")

    def assert_untouched(self):
        self.assertEqual(0, self.snapshot()["version"])
        self.assertEqual(0, self.db.execute(
            "SELECT count(*) FROM review_payment_events").fetchone()[0])

    def test_paid_projection_and_completed_lesson_conservation(self):
        result = self.send()
        self.assertEqual(("PAID", "ACTIVE", 2, 3, 1),
                         tuple(result["snapshot"][key] for key in
                               ("payment_state", "booking_state", "completed_lessons",
                                "remaining_bookable_lessons", "version")))

    def test_replayed_exact_payload_never_increments_version(self):
        self.send()
        replay = self.send()
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(1, replay["snapshot"]["version"])
        self.assertEqual(1, self.db.execute(
            "SELECT count(*) FROM review_payment_events").fetchone()[0])

    def test_forged_hmac_rejected_without_side_effects(self):
        args = signed(event())
        args["signature"] = "sha256=" + "0" * 64
        with self.assertRaises(ValueError):
            apply_test_signed_event(self.db, **args)
        self.assert_untouched()

    def test_mismatched_test_key_rejected(self):
        args = signed(event())
        args["test_key"] = b"another-unrelated-test-key-material-over-32"
        with self.assertRaises(ValueError):
            apply_test_signed_event(self.db, **args)
        self.assert_untouched()

    def test_malformed_header_and_weak_key_rejected(self):
        args = signed(event())
        for header in ("sha256=bad", "SHA256=" + "0"*64, "sha256=" + "A"*64):
            with self.subTest(header=header), self.assertRaises(ValueError):
                apply_test_signed_event(self.db, payload=args["payload"],
                                        signature=header, test_key=TEST_KEY)
        with self.assertRaises(ValueError):
            apply_test_signed_event(self.db, **signed(event(), key=b"weak"))
        self.assert_untouched()

    def test_duplicate_json_field_rejected_even_when_signed(self):
        payload = (b'{"source":"TEST_SIGNED_PROVIDER_SIMULATOR",'
                   b'"booking_id":"booking_1","payment_id":"payment_1",'
                   b'"event_id":"evt_1","sequence":1,"outcome":"SUCCESS",'
                   b'"outcome":"CANCELED"}')
        signature = "sha256=" + hmac.new(TEST_KEY, payload, hashlib.sha256).hexdigest()
        with self.assertRaises(ValueError):
            apply_test_signed_event(self.db, payload=payload,
                                    signature=signature, test_key=TEST_KEY)
        self.assert_untouched()

    def test_extra_field_and_missing_field_fail_closed(self):
        for bad in (event(approved=True),
                    {k: v for k, v in event().items() if k != "payment_id"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                apply_test_signed_event(self.db, **signed(bad))
        self.assert_untouched()

    def test_source_spoof_rejected(self):
        with self.assertRaises(ValueError):
            self.send(source="ACTUAL_PROVIDER")
        self.assert_untouched()

    def test_cross_booking_payment_rejected(self):
        with self.assertRaises(ValueError):
            self.send(payment_id="payment_other")
        self.assert_untouched()

    def test_unknown_booking_rejected(self):
        with self.assertRaises(ValueError):
            self.send(booking_id="booking_other")
        self.assert_untouched()

    def test_event_id_conflicting_replay_rolls_back(self):
        self.send()
        with self.assertRaises(ValueError):
            self.send(outcome="CANCELED")
        self.assertEqual(1, self.snapshot()["version"])

    def test_duplicate_sequence_conflict_rolls_back(self):
        self.send()
        with self.assertRaises(ValueError):
            self.send(event_id="evt_2", outcome="CANCELED")
        self.assertEqual(1, self.snapshot()["version"])
        self.assertEqual(1, self.db.execute(
            "SELECT count(*) FROM review_payment_events").fetchone()[0])

    def test_out_of_order_cancel_then_success_requires_review(self):
        self.send(event_id="evt_2", sequence=2, outcome="CANCELED")
        result = self.send()
        self.assertEqual("REVIEW_REQUIRED", result["snapshot"]["booking_state"])
        self.assertEqual(0, result["snapshot"]["remaining_bookable_lessons"])
        self.assertEqual(2, result["snapshot"]["completed_lessons"])

    def test_cancellation_after_paid_preserves_completed_lessons(self):
        self.send()
        result = self.send(event_id="evt_2", sequence=2, outcome="CANCELED")
        self.assertEqual(2, result["snapshot"]["completed_lessons"])
        self.assertEqual(0, result["snapshot"]["remaining_bookable_lessons"])
        self.assertEqual("REVIEW_REQUIRED", result["snapshot"]["booking_state"])

    def test_failed_timeout_and_cancelled_never_unlock_lessons(self):
        for outcome in ("FAILURE", "TIMEOUT", "CANCELED"):
            with self.subTest(outcome=outcome):
                db = sqlite3.connect(":memory:")
                try:
                    initialize_review_db(db)
                    seed_review_booking(db, booking_id="booking_1",
                                        payment_id="payment_1", lesson_count=5)
                    result = apply_test_signed_event(db, **signed(event(outcome=outcome)))
                    self.assertEqual(0, result["snapshot"]["remaining_bookable_lessons"])
                finally:
                    db.close()

    def test_invalid_outcome_rolls_back(self):
        with self.assertRaises(ValueError):
            self.send(outcome="REFUNDED")
        self.assert_untouched()

    def test_boolean_sequence_is_not_accepted_as_integer(self):
        with self.assertRaises(ValueError):
            self.send(sequence=True)
        self.assert_untouched()

    def test_unbindable_event_id_list_rejected_as_validation_error(self):
        # Untrusted JSON array must not leak sqlite3.ProgrammingError to caller.
        with self.assertRaises(ValueError):
            self.send(event_id=["evt_1"])
        self.assert_untouched()

    def test_unbindable_booking_id_list_rejected_as_validation_error(self):
        # Validate the JSON schema before binding booking_id into SQLite.
        with self.assertRaises(ValueError):
            self.send(booking_id=["booking_1"])
        self.assert_untouched()

    def test_sqlite_trigger_failure_rolls_back_insert_and_update(self):
        self.db.execute("""CREATE TRIGGER abort_booking_update
            BEFORE UPDATE ON review_bookings BEGIN
              SELECT RAISE(ABORT, 'B independent forced rollback');
            END""")
        with self.assertRaises(sqlite3.DatabaseError):
            self.send()
        self.assert_untouched()

    def test_second_booking_isolated_from_first_booking_events(self):
        seed_review_booking(self.db, booking_id="booking_2",
                            payment_id="payment_2", lesson_count=2)
        self.send()
        other = apply_test_signed_event(self.db, **signed(event(
            booking_id="booking_2", payment_id="payment_2", event_id="evt_2")))
        self.assertEqual(1, other["snapshot"]["version"])
        self.assertEqual(1, self.snapshot()["version"])
        self.assertEqual(2, self.db.execute(
            "SELECT count(*) FROM review_payment_events").fetchone()[0])

    def test_file_backed_restart_preserves_idempotency(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "bqa-review.sqlite")
            db = sqlite3.connect(path)
            try:
                initialize_review_db(db)
                seed_review_booking(db, booking_id="booking_1",
                                    payment_id="payment_1", lesson_count=2)
                apply_test_signed_event(db, **signed(event()))
            finally:
                db.close()
            db = sqlite3.connect(path)
            try:
                replay = apply_test_signed_event(db, **signed(event()))
                self.assertTrue(replay["idempotent_replay"])
                self.assertEqual(1, replay["snapshot"]["version"])
            finally:
                db.close()

    def test_review_only_flags_never_claim_provider_or_money_authorization(self):
        result = self.send()
        self.assertTrue(result["simulator_signature_checked"])
        self.assertTrue(result["atomic_review_db_update"])
        for flag in ("payment_event_provenance_verified", "operating_db_connected",
                     "production_booking_updated", "real_money_enabled",
                     "provider_api_called", "authenticated_user_api_connected"):
            self.assertIs(result[flag], False, flag)

    def test_invalid_utf8_payload_rejected_without_write(self):
        payload = b"\xff\xfe"
        signature = "sha256=" + hmac.new(TEST_KEY, payload, hashlib.sha256).hexdigest()
        with self.assertRaises(ValueError):
            apply_test_signed_event(self.db, payload=payload,
                                    signature=signature, test_key=TEST_KEY)
        self.assert_untouched()


    def test_all_three_ids_reject_non_scalar_json_types_before_sql(self):
        for field in ("booking_id", "payment_id", "event_id"):
            for invalid in (["booking_1"], {"id": "booking_1"}, None, True, 123, 1.25):
                with self.subTest(field=field, invalid=invalid):
                    candidate = event()
                    candidate[field] = invalid
                    with self.assertRaises(ValueError):
                        apply_test_signed_event(self.db, **signed(candidate))
                    self.assert_untouched()

    def test_all_three_ids_reject_bad_strings_before_sql(self):
        for field in ("booking_id", "payment_id", "event_id"):
            for invalid in ("", " space", "bad/path", "x" * 65, "newline\\n", "한글"):
                with self.subTest(field=field, invalid=invalid):
                    candidate = event()
                    candidate[field] = invalid
                    with self.assertRaises(ValueError):
                        apply_test_signed_event(self.db, **signed(candidate))
                    self.assert_untouched()

    def test_snapshot_id_input_validation_is_fail_closed(self):
        for invalid in (["booking_1"], {"id": "booking_1"}, None, True, 123,
                        "", "bad/path", "x" * 65):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                read_review_snapshot(self.db, booking_id=invalid)
        self.assert_untouched()


if __name__ == "__main__":
    unittest.main()
