import unittest
from team14_persistent import MonthlyStore,SimError
from team14_booking_events import apply_booking_event
class RefundEventValidationTests(unittest.TestCase):
 def setUp(self):
  self.s=MonthlyStore()
  self.s.create_month('m',[('l','b',101)])
  self.s.event('m','l','b','tx1','op1','complete')
 def tearDown(self):self.s.close()
 def event(self,action,amount,tx='tx2',eid='ev2'):
  return dict(event_id=eid,month_id='m',lesson_id='l',booking_id='b',transaction_id=tx,action=action,booking_status='refunded',currency='KRW',amount_krw=amount)
 def test_completed_refund_adapter(self):
  self.assertEqual(apply_booking_event(self.s,self.event('refund_completed',33))['state'],'completed_partially_refunded')
 def test_zero_completed_refund_rejected(self):
  with self.assertRaises(SimError):apply_booking_event(self.s,self.event('refund_completed',0))
 def test_bool_completed_refund_rejected(self):
  with self.assertRaises(SimError):apply_booking_event(self.s,self.event('refund_completed',True))
 def test_overflow_completed_refund_rejected(self):
  with self.assertRaises(SimError):apply_booking_event(self.s,self.event('refund_completed',102))
 def test_invalid_action_rejected(self):
  with self.assertRaises(SimError):apply_booking_event(self.s,self.event('payout',33))
 def test_completed_refund_replay(self):
  e=self.event('refund_completed',33)
  apply_booking_event(self.s,e)
  self.assertEqual(apply_booking_event(self.s,e)['state'],'completed_partially_refunded')
  self.assertEqual(self.s.db.execute("SELECT COUNT(*) FROM ledger WHERE kind LIKE '%reversal'").fetchone()[0],4)
 def test_complete_cannot_have_amount(self):
  e=self.event('complete',33);e['booking_status']='completed'
  with self.assertRaises(SimError):apply_booking_event(self.s,e)
if __name__=='__main__':unittest.main()
