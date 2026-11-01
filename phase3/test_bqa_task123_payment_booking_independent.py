"""B/15 QA-only exact-SHA adversarial review for #123 product 7d45b6485c600db342815c75240916349a3fa77f.
No production changes or real-money claims. Isolated state projection only.
"""
import copy
import unittest

from team14_payment_booking_projection import reconcile_payment_booking


def booking(count=4, completed=0):
    return {"booking_id": "bk_123", "payment_id": "pay_123",
            "lesson_count": count, "completed_lessons": completed}


def event(outcome, sequence=1, event_id=None, payment_id="pay_123"):
    return {"event_id": event_id or ("evt_" + str(sequence)),
            "payment_id": payment_id, "sequence": sequence, "outcome": outcome}


def project(events=(), *, count=4, completed=0):
    return reconcile_payment_booking(booking=booking(count, completed), events=events)


class BIndependentPaymentBooking123(unittest.TestCase):
    def assert_never_live(self, r):
        self.assertEqual(123, r["task"])
        self.assertEqual("ISOLATED_REVIEW_ONLY", r["status"])
        for k in ("payment_event_provenance_verified", "operating_db_connected",
                  "real_money_enabled", "provider_api_called", "production_booking_updated"):
            self.assertIs(r[k], False, k)

    def test_no_payment_no_unlocked_lessons(self):
        r = project()
        self.assertEqual(("PENDING", "AWAITING_PAYMENT", 0),
                         (r["payment_state"], r["booking_state"], r["remaining_bookable_lessons"]))
        self.assert_never_live(r)

    def test_single_success_unblocks_only_uncompleted_lessons(self):
        r = project([event("SUCCESS")], count=8, completed=3)
        self.assertEqual(("PAID", "ACTIVE", 5),
                         (r["payment_state"], r["booking_state"], r["remaining_bookable_lessons"]))
        self.assertEqual(3, r["completed_lessons"])
        self.assert_never_live(r)

    def test_success_when_fully_completed(self):
        r = project([event("SUCCESS")], count=4, completed=4)
        self.assertEqual("COMPLETED", r["booking_state"])
        self.assertEqual(0, r["remaining_bookable_lessons"])

    def test_terminal_failure_timeout_and_cancel_fail_closed(self):
        expected = {"FAILURE": "PAYMENT_FAILED", "TIMEOUT": "PAYMENT_TIMED_OUT",
                    "CANCELED": "CANCELED"}
        for outcome, state in expected.items():
            with self.subTest(outcome=outcome):
                r = project([event(outcome)])
                self.assertEqual(state, r["booking_state"])
                self.assertEqual(0, r["remaining_bookable_lessons"])

    def test_cancel_paid_booking_preserves_completed_history(self):
        r = project([event("CANCELED", 2), event("SUCCESS", 1)], completed=2)
        self.assertEqual("REVIEW_REQUIRED", r["booking_state"])
        self.assertTrue(r["manual_review_required"])
        self.assertEqual(2, r["completed_lessons"])
        self.assertEqual(0, r["remaining_bookable_lessons"])

    def test_out_of_order_delivery_has_identical_projection(self):
        events = [event("SUCCESS", 1), event("CANCELED", 2)]
        self.assertEqual(project(events), project(list(reversed(events))))

    def test_replayed_identical_event_id_is_idempotent(self):
        e = event("SUCCESS", 7)
        r = project([e, copy.deepcopy(e), e])
        self.assertEqual(1, r["unique_event_count"])
        self.assertEqual("PAID", r["payment_state"])

    def test_duplicate_sequence_distinct_ids_rejected(self):
        with self.assertRaises(ValueError):
            project([event("SUCCESS", 1, "evt_A"), event("FAILURE", 1, "evt_B")])

    def test_conflicting_event_id_rejected(self):
        with self.assertRaises(ValueError):
            project([event("SUCCESS", 1, "evt_A"), event("CANCELED", 2, "evt_A")])

    def test_paid_then_duplicate_success_is_disputed(self):
        r = project([event("SUCCESS", 1), event("SUCCESS", 2)])
        self.assertEqual("DISPUTED", r["payment_state"])
        self.assertEqual("REVIEW_REQUIRED", r["booking_state"])
        self.assertEqual(0, r["remaining_bookable_lessons"])

    def test_failure_then_success_never_revives_automatically(self):
        for outcome in ("FAILURE", "TIMEOUT", "CANCELED"):
            with self.subTest(outcome=outcome):
                r = project([event(outcome, 1), event("SUCCESS", 2)])
                self.assertEqual("DISPUTED", r["payment_state"])
                self.assertEqual(0, r["remaining_bookable_lessons"])

    def test_cross_payment_event_rejected(self):
        with self.assertRaises(ValueError):
            project([event("SUCCESS", payment_id="other_payment")])

    def test_invalid_lesson_counts_and_boolean_spoof_rejected(self):
        for value in (True, -1, "3", None, 1001):
            with self.subTest(value=value), self.assertRaises(ValueError):
                reconcile_payment_booking(booking=dict(booking(), completed_lessons=value), events=[])
        with self.assertRaises(ValueError):
            project([], count=2, completed=3)

    def test_untrusted_fields_and_unknown_event_outcomes_rejected(self):
        for bad in ("PAID", "REFUNDED", "", None):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                project([event(bad)])
        with self.assertRaises(ValueError):
            project([dict(event("SUCCESS"), signature_verified=True)])
        with self.assertRaises(ValueError):
            reconcile_payment_booking(booking=dict(booking(), payout_enabled=True), events=[])

    def test_too_many_events_fail_closed(self):
        with self.assertRaises(ValueError):
            project([event("SUCCESS", 1)] * 1001)

    def test_no_mutation_and_determinism(self):
        b, es = booking(), [event("SUCCESS")]
        snapshot = copy.deepcopy((b, es))
        a = reconcile_payment_booking(booking=b, events=es)
        self.assertEqual(a, reconcile_payment_booking(booking=b, events=es))
        self.assertEqual(snapshot, (b, es))
        self.assert_never_live(a)

    def test_paid_does_not_claim_real_event_provenance(self):
        self.assert_never_live(project([event("SUCCESS")]))


if __name__ == "__main__":
    unittest.main()
