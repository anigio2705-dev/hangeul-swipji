"""#123 isolated booking-payment projection regression and fail-closed tests."""
from copy import deepcopy
import unittest

from team14_booking_payment_projection import project_booking_payment


def event(number, kind="succeeded", booking="book123", identifier=None):
    return {"id": identifier or "evt_" + str(number), "booking_id": booking,
            "sequence": number, "kind": kind}


def project(**changes):
    values = dict(booking_id="book123", purchased_lessons=5, consumed_lessons=1,
                  payment_events=[event(1)], trusted_provider_event_verified=True,
                  booking_owner_verified=True)
    values.update(changes)
    return project_booking_payment(**values)


class Task123BookingPaymentTests(unittest.TestCase):
    def test_success_sets_preview_remaining_lessons_only(self):
        result = project()
        self.assertEqual(("PAID", "REVIEW_ONLY", 4),
                         (result["payment_state_preview"], result["preview_status"],
                          result["remaining_lessons_preview"]))
        self.assertTrue(result["would_be_schedulable_if_integrated"])
        self.assertFalse(result["can_schedule"])

    def test_failed_payment_does_not_unlock_lessons(self):
        result = project(consumed_lessons=0, payment_events=[event(1, "failed")])
        self.assertEqual("FAILED", result["payment_state_preview"])
        self.assertEqual(0, result["remaining_lessons_preview"])

    def test_timeout_does_not_unlock_lessons(self):
        result = project(consumed_lessons=0, payment_events=[event(1, "timed_out")])
        self.assertEqual("TIMED_OUT", result["payment_state_preview"])
        self.assertFalse(result["would_be_schedulable_if_integrated"])

    def test_cancelled_before_payment_is_not_paid(self):
        result = project(consumed_lessons=0, payment_events=[event(1, "cancelled")])
        self.assertEqual("CANCELLED", result["payment_state_preview"])
        self.assertEqual(0, result["remaining_lessons_preview"])

    def test_paid_then_cancelled_requires_review_not_auto_refund(self):
        result = project(payment_events=[event(1), event(2, "cancelled")])
        self.assertEqual("CANCELLATION_REVIEW", result["payment_state_preview"])
        self.assertIn("PAID_BOOKING_CANCELLATION_REQUIRES_REVIEW", result["reasons"])
        self.assertFalse(result["can_refund"])

    def test_late_success_after_timeout_cannot_resurrect(self):
        result = project(consumed_lessons=0,
                         payment_events=[event(1, "timed_out"), event(2, "succeeded")])
        self.assertEqual("REVIEW_REQUIRED", result["payment_state_preview"])
        self.assertEqual(0, result["remaining_lessons_preview"])

    def test_late_success_after_failure_cannot_resurrect(self):
        result = project(consumed_lessons=0,
                         payment_events=[event(1, "failed"), event(2, "succeeded")])
        self.assertEqual("REVIEW_REQUIRED", result["payment_state_preview"])

    def test_out_of_order_input_is_sorted_by_sequence(self):
        result = project(consumed_lessons=0,
                         payment_events=[event(2, "cancelled"), event(1)])
        self.assertEqual("CANCELLATION_REVIEW", result["payment_state_preview"])

    def test_missing_sequence_holds(self):
        result = project(consumed_lessons=0, payment_events=[event(2)])
        self.assertIn("EVENT_SEQUENCE_GAP", result["reasons"])
        self.assertEqual(0, result["remaining_lessons_preview"])

    def test_duplicate_sequence_and_event_id_hold(self):
        for events in ([event(1), event(1, identifier="another")],
                       [event(1), event(2, identifier="evt_1")]):
            with self.subTest(events=events):
                result = project(payment_events=events)
                self.assertEqual("HOLD", result["preview_status"])
                self.assertEqual(0, result["remaining_lessons_preview"])

    def test_foreign_booking_event_holds(self):
        result = project(payment_events=[event(1, booking="other")])
        self.assertIn("FOREIGN_BOOKING_EVENT", result["reasons"])
        self.assertFalse(result["can_schedule"])

    def test_untrusted_provider_or_owner_holds(self):
        for key in ("trusted_provider_event_verified", "booking_owner_verified"):
            result = project(**{key: False})
            self.assertEqual("HOLD", result["preview_status"])
            self.assertEqual(0, result["remaining_lessons_preview"])

    def test_invalid_flag_types_fail_closed(self):
        for value in (1, 0, None, "true", [], {}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                project(trusted_provider_event_verified=value)

    def test_invalid_counts_fail_closed(self):
        for value in (True, -1, 1.0, "3", None, 1001):
            with self.subTest(value=value), self.assertRaises(ValueError):
                project(purchased_lessons=value)
        with self.assertRaises(ValueError):
            project(consumed_lessons=6)

    def test_bad_event_schema_or_identity_rejected(self):
        for events in ([{"id": "x"}],
                       [event(1, identifier="../forged")],
                       [{**event(1), "extra": True}],
                       [{**event(1), "sequence": True}],
                       [{**event(1), "kind": "charge"}]):
            with self.subTest(events=events), self.assertRaises(ValueError):
                project(payment_events=events)

    def test_zero_purchased_lessons_never_schedulable(self):
        result = project(purchased_lessons=0, consumed_lessons=0)
        self.assertIn("PAID_WITH_ZERO_PURCHASED_LESSONS", result["reasons"])
        self.assertFalse(result["would_be_schedulable_if_integrated"])

    def test_empty_events_pending(self):
        result = project(consumed_lessons=0, payment_events=[])
        self.assertEqual("PENDING", result["payment_state_preview"])
        self.assertEqual("HOLD", result["preview_status"])

    def test_inputs_immutable_and_no_money_or_db(self):
        events = [event(1)]
        before = deepcopy(events)
        result = project(payment_events=events)
        self.assertEqual(before, events)
        for key in ("can_schedule", "can_charge", "can_refund", "can_payout",
                    "operating_db_connected", "provider_connected"):
            self.assertIs(result[key], False)


if __name__ == "__main__":
    unittest.main()
