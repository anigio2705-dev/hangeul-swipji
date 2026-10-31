"""Independent B/15 adversarial QA for #124 product SHA
748295d541dd4873b1ddf590779aaec4e03bd9e4.
QA-only: isolated temporary SQLite, no real payments or external requests.
"""
import json
import os
import tempfile
import unittest

from team14_mock_webhook_inbox import MockWebhookInbox, sign_fixture

SECRET = b"independent-bqa-124-test-secret-32"


def event(event_id="event1", booking_id="booking1", sequence=1, status="pending"):
    return json.dumps(dict(event_id=event_id, booking_id=booking_id,
                           sequence=sequence, status=status),
                      sort_keys=True, separators=(",", ":")).encode("utf-8")


class IndependentWebhookInboxQA(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "isolated.sqlite")
        self.inbox = MockWebhookInbox(self.path, SECRET)

    def tearDown(self):
        self.inbox.close()
        self.tmp.cleanup()

    def send(self, raw):
        return self.inbox.ingest(raw, sign_fixture(SECRET, raw))

    def test_01_exact_signed_bytes_and_tamper(self):
        original = event()
        with self.assertRaises(ValueError):
            self.inbox.ingest(event(status="succeeded"), sign_fixture(SECRET, original))
        self.assertIsNone(self.inbox.snapshot("booking1"))
        self.assertEqual("APPLIED", self.send(original)["result"])

    def test_02_conflicting_signed_event_id_never_overwrites(self):
        self.send(event())
        with self.assertRaises(ValueError):
            self.send(event(status="failed"))
        self.assertEqual({"sequence": 1, "status": "pending"},
                         self.inbox.snapshot("booking1"))

    def test_03_sequence_collision_after_gap_rolls_back(self):
        self.assertEqual("WAIT_MISSING",
                         self.send(event("event3", sequence=3))["result"])
        with self.assertRaises(ValueError):
            self.send(event("event4", sequence=3, status="failed"))
        self.assertEqual(1, self.inbox.reprocess("booking1")["pending"])
        self.send(event("event1", sequence=1))
        self.send(event("event2", sequence=2, status="succeeded"))
        self.assertEqual({"sequence": 3, "status": "pending"},
                         self.inbox.snapshot("booking1"))

    def test_04_restart_replay_does_not_advance(self):
        raw = event("event2", sequence=2)
        self.send(raw)
        self.inbox.close()
        self.inbox = MockWebhookInbox(self.path, SECRET)
        self.assertEqual("DUPLICATE", self.send(raw)["result"])
        self.send(event())
        self.assertEqual(2, self.inbox.snapshot("booking1")["sequence"])
        self.assertEqual(0, self.inbox.reprocess("booking1")["pending"])

    def test_05_booking_isolation_with_same_sequence(self):
        self.send(event("other1", "booking2", 1, "failed"))
        self.send(event("event1", "booking1", 1, "succeeded"))
        self.assertEqual("failed", self.inbox.snapshot("booking2")["status"])
        self.assertEqual("succeeded", self.inbox.snapshot("booking1")["status"])

    def test_06_signed_unknown_field_rejected(self):
        raw = b'{"event_id":"event1","booking_id":"booking1","sequence":1,"status":"pending","amount":9999}'
        with self.assertRaises(ValueError):
            self.send(raw)
        self.assertIsNone(self.inbox.snapshot("booking1"))

    def test_07_signed_duplicate_json_key_rejected(self):
        """Duplicate member names create parser ambiguity despite a valid HMAC.
        A strict exact-schema webhook should reject them before state mutation.
        """
        raw = b'{"event_id":"first","event_id":"second","booking_id":"booking1","sequence":1,"status":"pending"}'
        with self.assertRaises(ValueError):
            self.send(raw)
        self.assertIsNone(self.inbox.snapshot("booking1"))

    def test_08_signed_duplicate_sequence_key_rejected(self):
        raw = b'{"event_id":"event1","booking_id":"booking1","sequence":999,"sequence":1,"status":"pending"}'
        with self.assertRaises(ValueError):
            self.send(raw)
        self.assertIsNone(self.inbox.snapshot("booking1"))

    def test_09_invalid_utf8_and_null_bytes_rejected(self):
        for raw in (bytes([0xff]), b'{"event_id":"event1"}' + bytes([0])):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.send(raw)
        self.assertIsNone(self.inbox.snapshot("booking1"))

    def test_10_signed_path_like_identifier_rejected(self):
        raw = event(event_id="../forged")
        with self.assertRaises(ValueError):
            self.send(raw)
        self.assertIsNone(self.inbox.snapshot("booking1"))

    def test_11_rejected_payload_does_not_poison_valid_followup(self):
        with self.assertRaises(ValueError):
            self.send(event(status="charged"))
        self.assertEqual("APPLIED", self.send(event())["result"])
        self.assertEqual("DUPLICATE", self.send(event())["result"])


if __name__ == "__main__":
    unittest.main()
