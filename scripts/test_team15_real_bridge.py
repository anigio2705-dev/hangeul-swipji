#!/usr/bin/env python3
"""Executable Team11 authorization -> Team14 verified mock ledger integration.

Uses real functions imported from independently checked-out team branches and a
temporary SQLite database. No public HTTP endpoint, live money or video.
Team13 server event provenance is NOT demonstrated by this isolated test.
"""
import importlib
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
for team in ("team11", "team14"):
    sys.path.insert(0, str(ROOT / team / "phase3"))
from team11_booking_access import booking_access
from team14_persistent import MonthlyStore, SimError
from team14_verified_bridge import apply_verified_booking_event

class RealFunctionBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dbpath = os.path.join(self.tmp.name, "mock.sqlite3")
        self.store = MonthlyStore(self.dbpath)
        self.store.create_month("month_1", [("lesson_1", "booking_1", 10001)])
        self.booking = dict(booking_id="booking_1", month_id="month_1",
                            lesson_id="lesson_1", learner_id="student_1",
                            teacher_id="teacher_1", teacher_approved=True,
                            booking_status="completed", authenticated_event=True)
        self.event = dict(event_id="event_1", month_id="month_1",
                          lesson_id="lesson_1", booking_id="booking_1",
                          transaction_id="txn_1", action="complete",
                          booking_status="completed", currency="KRW", amount_krw=0)
    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()
    def resolve(self, booking_id):
        return dict(self.booking) if booking_id == "booking_1" else None
    def test_actual_functions_and_sqlite_reopen(self):
        first = apply_verified_booking_event(self.store, self.event, self.resolve)
        self.assertEqual(first["state"], "completed")
        self.assertFalse(first["real_money"])
        before = self.store.totals("month_1")
        self.assertEqual(before["teacher"] + before["referral"] + before["platform"], 10001)
        self.store.close()
        self.store = MonthlyStore(self.dbpath)
        self.assertEqual(self.store.totals("month_1"), before)
        self.assertEqual(apply_verified_booking_event(self.store, self.event, self.resolve), first)
        self.assertEqual(self.store.totals("month_1"), before)
    def test_forged_event_is_denied_without_ledger_write(self):
        self.booking["authenticated_event"] = False
        with self.assertRaises(SimError) as ctx:
            apply_verified_booking_event(self.store, self.event, self.resolve)
        self.assertEqual(ctx.exception.code, "FORBIDDEN")
        self.assertEqual(self.store.totals("month_1")["teacher"], 0)
    def test_revoked_teacher_is_denied(self):
        self.booking["teacher_approved"] = False
        with self.assertRaises(SimError) as ctx:
            apply_verified_booking_event(self.store, self.event, self.resolve)
        self.assertEqual(ctx.exception.code, "FORBIDDEN")
    def test_mismatched_booking_denied(self):
        self.event["lesson_id"] = "lesson_other"
        with self.assertRaises(SimError) as ctx:
            apply_verified_booking_event(self.store, self.event, self.resolve)
        self.assertEqual(ctx.exception.code, "FORBIDDEN")
    def test_refund_completed_reverses_three_party_ledger(self):
        apply_verified_booking_event(self.store, self.event, self.resolve)
        self.booking["booking_status"] = "refunded"
        self.event.update(event_id="event_2", transaction_id="txn_2",
                          action="refund_completed", booking_status="refunded", amount_krw=10001)
        apply_verified_booking_event(self.store, self.event, self.resolve)
        totals = self.store.totals("month_1")
        self.assertEqual((totals["teacher"], totals["referral"], totals["platform"]), (0, 0, 0))
        self.assertEqual(totals["refunded"], 10001)
        self.assertFalse(totals["real_money"])
    def test_authorization_function_is_real_and_fails_closed(self):
        # Invalid action must be denied without any client-provided role assumptions.
        result = booking_access({}, {}, {}, "intruder", "settle")
        self.assertFalse(result["allowed"])
        self.assertEqual(result["code"], "VALIDATION_ERROR" if result["code"] == "VALIDATION_ERROR" else "FORBIDDEN")

if __name__ == "__main__":
    unittest.main(verbosity=2)
