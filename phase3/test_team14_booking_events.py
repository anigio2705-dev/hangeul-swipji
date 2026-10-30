import unittest
from team14_persistent import MonthlyStore,SimError
from team14_booking_events import apply_booking_event
class BookingEventTests(unittest.TestCase):
 def setUp(self):
  self.s=MonthlyStore()
  self.s.create_month("month1",[("lesson1","booking1",20000),("lesson2","booking2",20000)])
 def tearDown(self): self.s.close()
 def payload(self,**updates):
  e=dict(event_id="event1",month_id="month1",lesson_id="lesson1",booking_id="booking1",transaction_id="tx1",action="complete",booking_status="completed",currency="KRW",amount_krw=0)
  e.update(updates);return e
 def test_complete_and_replay(self):
  e=self.payload()
  self.assertEqual(apply_booking_event(self.s,e)["state"],"completed")
  self.assertEqual(apply_booking_event(self.s,e)["state"],"completed")
  self.assertEqual(self.s.db.execute("SELECT COUNT(*) FROM ledger").fetchone()[0],3)
 def test_reused_event_conflict(self):
  apply_booking_event(self.s,self.payload())
  with self.assertRaises(SimError) as ctx:apply_booking_event(self.s,self.payload(lesson_id="lesson2",booking_id="booking2",transaction_id="tx2"))
  self.assertEqual(ctx.exception.code,"CONFLICT")
 def test_booking_mismatch(self):
  with self.assertRaises(SimError) as ctx:apply_booking_event(self.s,self.payload(booking_id="booking2"))
  self.assertEqual(ctx.exception.code,"NOT_FOUND")
 def test_bad_currency_and_state(self):
  for e in (self.payload(currency="USD"),self.payload(booking_status="in_class")):
   with self.assertRaises(SimError):apply_booking_event(self.s,e)
 def test_partial_refund_then_cancel_rejected(self):
  e=self.payload(action="refund",booking_status="refunded",amount_krw=5000)
  self.assertEqual(apply_booking_event(self.s,e)["state"],"partially_refunded")
  with self.assertRaises(SimError):apply_booking_event(self.s,self.payload(event_id="event2",transaction_id="tx2",action="cancel",booking_status="cancelled"))
 def test_cancel_and_retry(self):
  e=self.payload(action="cancel",booking_status="cancelled")
  self.assertEqual(apply_booking_event(self.s,e)["state"],"cancelled")
  self.assertEqual(apply_booking_event(self.s,e)["state"],"cancelled")
  self.assertEqual(self.s.totals("month1")["refunded"],20000)
 def test_unknown_fields(self):
  with self.assertRaises(SimError):apply_booking_event(self.s,dict(self.payload(),secret="bad"))
 def test_reject_unrecognized_action(self):
  with self.assertRaises(SimError):apply_booking_event(self.s,self.payload(action="pay"))
 def test_partial_refund_status_matches_committed_state(self):
  # A 25% refund is not a fully refunded booking; a false status must fail closed.
  bad=self.payload(action="refund",booking_status="refunded",amount_krw=5000)
  with self.assertRaises(SimError) as ctx:apply_booking_event(self.s,bad)
  self.assertEqual(ctx.exception.code,"INVALID_STATE")
  self.assertEqual(self.s.db.execute("SELECT state FROM lessons WHERE id='lesson1'").fetchone()[0],"reserved")
  self.assertEqual(self.s.db.execute("SELECT COUNT(*) FROM ledger").fetchone()[0],0)
  partial=self.payload(booking_status="partially_refunded",action="refund",amount_krw=5000)
  self.assertEqual(apply_booking_event(self.s,partial)["state"],"partially_refunded")
  full=self.payload(event_id="event2",transaction_id="tx2",action="refund",booking_status="refunded",amount_krw=15000)
  self.assertEqual(apply_booking_event(self.s,full)["state"],"refunded")
  self.assertEqual(self.s.totals("month1")["refunded"],20000)
 def test_completed_partial_refund_requires_exact_status(self):
  apply_booking_event(self.s,self.payload())
  bad=self.payload(event_id="event2",transaction_id="tx2",action="refund_completed",booking_status="refunded",amount_krw=5000)
  with self.assertRaises(SimError) as ctx:apply_booking_event(self.s,bad)
  self.assertEqual(ctx.exception.code,"INVALID_STATE")
  self.assertEqual(self.s.db.execute("SELECT state FROM lessons WHERE id='lesson1'").fetchone()[0],"completed")
  partial=self.payload(event_id="event2",transaction_id="tx2",action="refund_completed",booking_status="completed_partially_refunded",amount_krw=5000)
  self.assertEqual(apply_booking_event(self.s,partial)["state"],"completed_partially_refunded")
  full=self.payload(event_id="event3",transaction_id="tx3",action="refund_completed",booking_status="refunded",amount_krw=15000)
  self.assertEqual(apply_booking_event(self.s,full)["state"],"refunded")
  totals=self.s.totals("month1")
  self.assertEqual((totals["refunded"],totals["teacher"],totals["referral"],totals["platform"]),(20000,0,0,0))
if __name__=="__main__":unittest.main()
