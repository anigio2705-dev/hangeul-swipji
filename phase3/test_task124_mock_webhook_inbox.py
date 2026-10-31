"""#124 regression suite: signed mock webhook inbox, no live money or provider."""
import json
import os
import tempfile
import unittest

from team14_mock_webhook_inbox import MockWebhookInbox, sign_fixture

KEY = b"mock-only-test-secret-32-bytes-long"


def payload(event_id="evt1", booking_id="book1", sequence=1, status="pending", **extra):
    data = dict(event_id=event_id, booking_id=booking_id,
                sequence=sequence, status=status)
    data.update(extra)
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()


class Task124WebhookInboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "mock-inbox.sqlite")
        self.inbox = MockWebhookInbox(self.path, KEY)

    def tearDown(self):
        self.inbox.close()
        self.temp.cleanup()

    def send(self, raw, signature=None):
        return self.inbox.ingest(raw, signature or sign_fixture(KEY, raw))

    def test_valid_signed_event_applies(self):
        self.assertEqual("APPLIED", self.send(payload())["result"])
        self.assertEqual({"sequence": 1, "status": "pending"},
                         self.inbox.snapshot("book1"))

    def test_identical_duplicate_is_idempotent(self):
        raw = payload()
        self.send(raw)
        self.assertEqual({"result": "DUPLICATE", "applied": 0}, self.send(raw))
        self.assertEqual(1, self.inbox.snapshot("book1")["sequence"])

    def test_tampered_signature_rejected_before_storage(self):
        raw = payload()
        with self.assertRaisesRegex(ValueError, "signature"):
            self.send(raw, "sha256=" + "0" * 64)
        self.assertIsNone(self.inbox.snapshot("book1"))

    def test_event_id_reused_with_altered_signed_payload_rejected(self):
        self.send(payload())
        with self.assertRaisesRegex(ValueError, "event id reused"):
            self.send(payload(status="failed"))
        self.assertEqual("pending", self.inbox.snapshot("book1")["status"])

    def test_sequence_conflict_different_event_id_rejected(self):
        self.send(payload())
        with self.assertRaisesRegex(ValueError, "stale sequence"):
            self.send(payload(event_id="evt2", status="failed"))

    def test_out_of_order_waits_then_drains_contiguous(self):
        second = payload(event_id="evt2", sequence=2, status="succeeded")
        self.assertEqual("WAIT_MISSING", self.send(second)["result"])
        self.assertIsNone(self.inbox.snapshot("book1"))
        self.assertEqual({"applied": 0, "pending": 1, "next_expected_sequence": 1},
                         self.inbox.reprocess("book1"))
        self.assertEqual({"result": "APPLIED", "applied": 2}, self.send(payload()))
        self.assertEqual({"sequence": 2, "status": "succeeded"},
                         self.inbox.snapshot("book1"))
        self.assertEqual("DUPLICATE", self.send(second)["result"])

    def test_missing_middle_event_reprocess(self):
        self.send(payload())
        self.send(payload(event_id="evt3", sequence=3, status="canceled"))
        self.assertEqual(2, self.inbox.reprocess("book1")["next_expected_sequence"])
        self.assertEqual(1, self.inbox.reprocess("book1")["pending"])
        self.send(payload(event_id="evt2", sequence=2, status="succeeded"))
        self.assertEqual({"sequence": 3, "status": "canceled"},
                         self.inbox.snapshot("book1"))

    def test_restart_preserves_gap_and_dedup(self):
        raw = payload(event_id="evt2", sequence=2)
        self.send(raw)
        self.inbox.close()
        self.inbox = MockWebhookInbox(self.path, KEY)
        self.assertEqual("DUPLICATE", self.send(raw)["result"])
        self.send(payload())
        self.assertEqual(2, self.inbox.snapshot("book1")["sequence"])

    def test_separate_bookings_are_isolated(self):
        self.send(payload(event_id="evt2", booking_id="book2", sequence=2))
        self.send(payload())
        self.assertIsNone(self.inbox.snapshot("book2"))
        self.assertEqual(1, self.inbox.snapshot("book1")["sequence"])

    def test_schema_rejects_extra_payment_card_data(self):
        with self.assertRaisesRegex(ValueError, "schema"):
            self.send(payload(card_number="4111111111111111"))
        self.assertIsNone(self.inbox.snapshot("book1"))

    def test_signed_duplicate_json_members_rejected_before_state_change(self):
        for raw in (
            b'{"event_id":"evt1","event_id":"evt2","booking_id":"book1","sequence":1,"status":"pending"}',
            b'{"event_id":"evt1","booking_id":"book1","sequence":99,"sequence":1,"status":"pending"}',
        ):
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, "JSON"):
                self.send(raw)
        self.assertIsNone(self.inbox.snapshot("book1"))

    def test_invalid_identifiers_and_bool_sequence_rejected(self):
        for raw in (payload(event_id="../forged"),
                    payload(booking_id="bad/path"),
                    payload(sequence=True),
                    payload(sequence=0),
                    payload(status="paid")):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    self.send(raw)

    def test_invalid_json_and_empty_secret_rejected(self):
        with self.assertRaises(ValueError):
            self.send(b"not-json")
        with self.assertRaises(ValueError):
            MockWebhookInbox(":memory:", b"weak")

    def test_failed_ingest_rolls_back_and_later_valid_event_works(self):
        self.send(payload())
        with self.assertRaises(ValueError):
            self.send(payload(event_id="evt2", sequence=1))
        self.assertEqual("APPLIED",
                         self.send(payload(event_id="evt2", sequence=2,
                                           status="failed"))["result"])
        self.assertEqual("failed", self.inbox.snapshot("book1")["status"])

    def test_no_actual_payment_or_booking_mutation(self):
        import inspect
        from team14_mock_webhook_inbox import MockWebhookInbox
        source = inspect.getsource(MockWebhookInbox)
        self.assertNotIn("requests.post", source)
        self.assertNotIn("urllib.request", source)
        self.assertNotIn("phase3/server.py", source)
        self.assertEqual({"sequence": 1, "status": "pending"},
                         (self.send(payload()), self.inbox.snapshot("book1"))[1])


if __name__ == "__main__":
    unittest.main()
