"""B/15 independent QA: original #123 booking/payment projection (exact product SHA).

Read-only adversarial regression matrix. No production code, network, DB or money.
"""
import copy
import unittest

from team14_booking_payment_projection import project_booking_payment


def event(seq, kind="succeeded", booking="booking_B", event_id=None):
    return {"id": event_id or "evt_" + str(seq),
            "booking_id": booking, "sequence": seq, "kind": kind}


def inspect(**override):
    payload = dict(booking_id="booking_B", purchased_lessons=8,
                   consumed_lessons=2, payment_events=[event(1)],
                   trusted_provider_event_verified=True,
                   booking_owner_verified=True)
    payload.update(override)
    return project_booking_payment(**payload)


class IndependentTask123QA(unittest.TestCase):
    def assert_no_execution(self, result):
        for key in ("can_schedule", "can_charge", "can_refund", "can_payout",
                    "operating_db_connected", "provider_connected"):
            self.assertIs(result[key], False, key)

    def assert_hold(self, result):
        self.assertEqual(result["preview_status"], "HOLD")
        self.assertEqual(result["remaining_lessons_preview"], 0)
        self.assertFalse(result["would_be_schedulable_if_integrated"])
        self.assert_no_execution(result)

    def test_01_paid_is_read_only_preview_not_booking_authorization(self):
        result = inspect()
        self.assertEqual(result["payment_state_preview"], "PAID")
        self.assertEqual(result["preview_status"], "REVIEW_ONLY")
        self.assertEqual(result["remaining_lessons_preview"], 6)
        self.assert_no_execution(result)

    def test_02_all_lessons_consumed_never_claims_schedulable(self):
        result = inspect(consumed_lessons=8)
        self.assertEqual(result["remaining_lessons_preview"], 0)
        self.assertFalse(result["would_be_schedulable_if_integrated"])
        self.assert_no_execution(result)

    def test_03_provider_and_owner_evidence_are_both_required(self):
        for provider, owner in ((False, True), (True, False), (False, False)):
            with self.subTest(provider=provider, owner=owner):
                result = inspect(trusted_provider_event_verified=provider,
                                 booking_owner_verified=owner)
                self.assert_hold(result)

    def test_04_boolean_spoofing_by_truthy_values_is_rejected(self):
        for key in ("trusted_provider_event_verified", "booking_owner_verified"):
            for bad in (1, 0, "true", None, [], {}):
                with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                    inspect(**{key: bad})

    def test_05_no_event_with_consumption_is_a_hold(self):
        result = inspect(payment_events=[])
        self.assert_hold(result)
        self.assertIn("CONSUMED_LESSONS_WITHOUT_VERIFIED_PAYMENT", result["reasons"])

    def test_06_failure_cancel_timeout_never_unlock_remaining_lessons(self):
        for kind in ("failed", "cancelled", "timed_out"):
            with self.subTest(kind=kind):
                self.assert_hold(inspect(consumed_lessons=0,
                                         payment_events=[event(1, kind)]))

    def test_07_paid_then_cancel_requires_review_not_refund(self):
        result = inspect(payment_events=[event(1), event(2, "cancelled")])
        self.assertEqual(result["payment_state_preview"], "CANCELLATION_REVIEW")
        self.assertIn("PAID_BOOKING_CANCELLATION_REQUIRES_REVIEW", result["reasons"])
        self.assert_hold(result)

    def test_08_late_success_after_terminal_event_cannot_resurrect(self):
        for first in ("failed", "cancelled", "timed_out"):
            with self.subTest(first=first):
                result = inspect(consumed_lessons=0,
                                 payment_events=[event(1, first), event(2)])
                self.assertEqual(result["payment_state_preview"], "REVIEW_REQUIRED")
                self.assert_hold(result)

    def test_09_replayed_id_or_duplicate_sequence_blocks_projection(self):
        for events in ([event(1), event(2, event_id="evt_1")],
                       [event(1), event(1, event_id="other")]):
            with self.subTest(events=events):
                self.assert_hold(inspect(payment_events=events))

    def test_10_missing_first_or_middle_sequence_blocks_projection(self):
        for events in ([event(2)], [event(1), event(3)]):
            with self.subTest(events=events):
                result = inspect(payment_events=events)
                self.assertIn("EVENT_SEQUENCE_GAP", result["reasons"])
                self.assert_hold(result)

    def test_11_foreign_booking_mixed_with_paid_event_fails_closed(self):
        result = inspect(payment_events=[event(1), event(2, booking="other_booking")])
        self.assertIn("FOREIGN_BOOKING_EVENT", result["reasons"])
        self.assert_hold(result)

    def test_12_out_of_order_delivery_uses_sequence_not_list_position(self):
        source = [event(2, "cancelled"), event(1)]
        snapshot = copy.deepcopy(source)
        result = inspect(payment_events=source)
        self.assertEqual(source, snapshot)
        self.assertEqual(result["payment_state_preview"], "CANCELLATION_REVIEW")
        self.assert_hold(result)

    def test_13_malformed_event_types_and_extra_fields_rejected(self):
        examples = ([None], [event(1) | {"extra": "injected"}],
                    [{**event(1), "sequence": True}],
                    [{**event(1), "kind": "refunded"}],
                    [{**event(1), "id": "../forged"}],
                    [{**event(1), "booking_id": ""}])
        for events in examples:
            with self.subTest(events=events), self.assertRaises(ValueError):
                inspect(payment_events=events)

    def test_14_booking_id_path_and_bad_types_rejected(self):
        for bad in ("", "../owner", "a/b", "x" * 65, 5, None, True):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                inspect(booking_id=bad)

    def test_15_counts_cannot_be_boolean_float_negative_or_overdrawn(self):
        for bad in (True, 1.0, "5", -1, 1001, None):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                inspect(consumed_lessons=bad)
        with self.assertRaises(ValueError):
            inspect(purchased_lessons=3, consumed_lessons=4)

    def test_16_event_list_limit_and_wrong_container_type(self):
        for bad in (tuple(), {}, None, [event(1)] * 101):
            with self.subTest(kind=type(bad).__name__), self.assertRaises(ValueError):
                inspect(payment_events=bad)

    def test_17_zero_purchased_lessons_never_grants_preview(self):
        result = inspect(purchased_lessons=0, consumed_lessons=0)
        self.assertIn("PAID_WITH_ZERO_PURCHASED_LESSONS", result["reasons"])
        self.assert_hold(result)

    def test_18_boundary_max_lessons_and_no_mutation(self):
        source = [event(1)]
        before = copy.deepcopy(source)
        result = inspect(purchased_lessons=1000, consumed_lessons=999,
                         payment_events=source)
        self.assertEqual(source, before)
        self.assertEqual(result["remaining_lessons_preview"], 1)
        self.assert_no_execution(result)


if __name__ == "__main__":
    unittest.main()
