"""A product regressions for original #123, isolated and never real-money."""
import copy
import unittest

from team14_payment_booking_projection import reconcile_payment_booking


def booking(completed=0, count=4):
    return {"booking_id": "booking_1", "payment_id": "payment_1",
            "lesson_count": count, "completed_lessons": completed}


def event(outcome, seq=1, event_id=None, payment_id="payment_1"):
    return {"event_id": event_id or ("event_" + str(seq)),
            "payment_id": payment_id, "sequence": seq, "outcome": outcome}


def run(events=(), *, completed=0, count=4):
    return reconcile_payment_booking(booking=booking(completed, count), events=events)


class PaymentBookingProjectionTests(unittest.TestCase):
    def assert_safe(self, r):
        self.assertEqual(123, r["task"])
        self.assertEqual("ISOLATED_REVIEW_ONLY", r["status"])
        for key in ("payment_event_provenance_verified", "operating_db_connected",
                    "real_money_enabled", "provider_api_called",
                    "production_booking_updated"):
            self.assertIs(r[key], False, key)

    def test_pending_no_entitlement(self):
        r = run()
        self.assertEqual(("PENDING", "AWAITING_PAYMENT", 0),
                         (r["payment_state"], r["booking_state"], r["remaining_bookable_lessons"]))
        self.assert_safe(r)

    def test_success_confirms_remaining_lessons(self):
        r = run([event("SUCCESS")], completed=1)
        self.assertEqual(("PAID", "ACTIVE", 3),
                         (r["payment_state"], r["booking_state"], r["remaining_bookable_lessons"]))
        self.assertFalse(r["manual_review_required"])
        self.assert_safe(r)

    def test_success_completed_all_lessons(self):
        r = run([event("SUCCESS")], completed=4)
        self.assertEqual("COMPLETED", r["booking_state"])
        self.assertEqual(0, r["remaining_bookable_lessons"])

    def test_failure_does_not_unlock_lessons(self):
        r = run([event("FAILURE")])
        self.assertEqual("PAYMENT_FAILED", r["booking_state"])
        self.assertEqual(0, r["remaining_bookable_lessons"])

    def test_timeout_does_not_unlock_lessons(self):
        r = run([event("TIMEOUT")])
        self.assertEqual("PAYMENT_TIMED_OUT", r["booking_state"])
        self.assertEqual(0, r["remaining_bookable_lessons"])

    def test_cancel_before_payment(self):
        r = run([event("CANCELED")])
        self.assertEqual("CANCELED", r["booking_state"])
        self.assertEqual(0, r["remaining_bookable_lessons"])

    def test_cancel_after_success_revokes_remaining_not_history(self):
        r = run([event("CANCELED", 2), event("SUCCESS", 1)], completed=2)
        self.assertEqual("CANCELED", r["payment_state"])
        self.assertEqual(0, r["remaining_bookable_lessons"])
        self.assertEqual(2, r["completed_lessons"])
        self.assertTrue(r["manual_review_required"])
        self.assertEqual("REVIEW_REQUIRED", r["booking_state"])

    def test_paid_then_failed_requires_manual_review(self):
        r = run([event("SUCCESS", 1), event("FAILURE", 2)])
        self.assertEqual("DISPUTED", r["payment_state"])
        self.assertTrue(r["manual_review_required"])
        self.assertEqual(0, r["remaining_bookable_lessons"])

    def test_failure_then_success_requires_manual_review(self):
        r = run([event("FAILURE", 1), event("SUCCESS", 2)])
        self.assertEqual("DISPUTED", r["payment_state"])
        self.assertEqual("REVIEW_REQUIRED", r["booking_state"])

    def test_timeout_then_success_requires_manual_review(self):
        r = run([event("TIMEOUT", 1), event("SUCCESS", 2)])
        self.assertEqual("DISPUTED", r["payment_state"])

    def test_cancel_then_success_never_revives(self):
        r = run([event("CANCELED", 1), event("SUCCESS", 2)])
        self.assertEqual("DISPUTED", r["payment_state"])
        self.assertEqual(0, r["remaining_bookable_lessons"])

    def test_duplicate_success_different_event_requires_review(self):
        r = run([event("SUCCESS", 1), event("SUCCESS", 2)])
        self.assertEqual("DISPUTED", r["payment_state"])

    def test_idempotent_replay_same_event_id(self):
        e = event("SUCCESS")
        r = run([e, copy.deepcopy(e), e])
        self.assertEqual("PAID", r["payment_state"])
        self.assertEqual(1, r["unique_event_count"])

    def test_out_of_order_delivery_uses_sequence(self):
        a = [event("SUCCESS", 1), event("CANCELED", 2)]
        self.assertEqual(run(a), run(list(reversed(a))))
        self.assertEqual([1, 2], [x["sequence"] for x in run(a)["ordered_event_history"]])

    def test_conflicting_duplicate_event_id_rejected(self):
        e = event("SUCCESS")
        with self.assertRaises(ValueError):
            run([e, {"event_id": e["event_id"], "payment_id": e["payment_id"],
                     "sequence": 2, "outcome": "CANCELED"}])

    def test_duplicate_sequence_different_id_rejected(self):
        with self.assertRaises(ValueError):
            run([event("SUCCESS", 1), event("FAILURE", 1, "other")])

    def test_cross_payment_event_rejected(self):
        with self.assertRaises(ValueError):
            run([event("SUCCESS", payment_id="other")])

    def test_completed_without_payment_requires_review(self):
        r = run([], completed=1)
        self.assertEqual("REVIEW_REQUIRED", r["booking_state"])
        self.assertEqual(0, r["remaining_bookable_lessons"])

    def test_reject_invalid_lesson_counts(self):
        for n in (True, "4", -1, 0, 1001, None, 1.5):
            with self.subTest(n=n), self.assertRaises(ValueError):
                run(count=n)
        for n in (True, "1", -1, 1001, None, 1.5, 5):
            with self.subTest(n=n), self.assertRaises(ValueError):
                run(completed=n)

    def test_reject_invalid_events_and_spoofed_fields(self):
        for bad in (None, {}, "SUCCESS", [None], [1], [event("SUCCESS", 0)],
                    [event("SUCCESS", -1)], [event("SUCCESS", 1, "")],
                    [dict(event("SUCCESS"), trusted=True)]):
            with self.subTest(bad=str(bad)[:70]), self.assertRaises(ValueError):
                run(bad)

    def test_reject_bad_outcome_and_untrusted_ids(self):
        for bad in ("PAID", "REFUND", "", None, 1, True):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                run([event(bad)])
        for bad in ("", "../admin", "x y", "x" * 65, None, 1):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                reconcile_payment_booking(
                    booking=dict(booking(), booking_id=bad), events=[])

    def test_reject_missing_extra_booking_fields(self):
        with self.assertRaises(ValueError):
            reconcile_payment_booking(booking={"booking_id": "x"}, events=[])
        with self.assertRaises(ValueError):
            reconcile_payment_booking(booking=dict(booking(), charge_now=True), events=[])

    def test_reject_event_overflow(self):
        with self.assertRaises(ValueError):
            run([event("SUCCESS")] * 1001)

    def test_deterministic_without_input_mutation(self):
        b, es = booking(), [event("SUCCESS")]
        snapshot = copy.deepcopy((b, es))
        a = reconcile_payment_booking(booking=b, events=es)
        self.assertEqual(a, reconcile_payment_booking(booking=b, events=es))
        self.assertEqual(snapshot, (b, es))
        self.assert_safe(a)


if __name__ == "__main__":
    unittest.main()
