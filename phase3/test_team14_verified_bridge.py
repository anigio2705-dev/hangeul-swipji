import unittest
from team14_persistent import MonthlyStore,SimError
from team14_verified_bridge import apply_verified_booking_event
class VerifiedBridgeTests(unittest.TestCase):
 def setUp(self):
  self.s=MonthlyStore()
  self.s.create_month('month1',[('lesson1','booking1',10000)])
  self.e=dict(event_id='ev1',month_id='month1',lesson_id='lesson1',booking_id='booking1',transaction_id='tx1',action='complete',booking_status='completed',currency='KRW',amount_krw=0)
  self.record=dict(booking_id='booking1',month_id='month1',lesson_id='lesson1',learner_id='student1',teacher_id='teacher1',teacher_approved=True,booking_status='completed',authenticated_event=True)
 def tearDown(self):self.s.close()
 def resolver(self,_):return dict(self.record)
 def test_verified_event_posts_once(self):
  self.assertEqual(apply_verified_booking_event(self.s,self.e,self.resolver)['state'],'completed')
  self.assertEqual(apply_verified_booking_event(self.s,self.e,self.resolver)['state'],'completed')
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0],3)
 def test_resolver_required(self):
  with self.assertRaises(SimError):apply_verified_booking_event(self.s,self.e,None)
 def test_unapproved_teacher(self):
  self.record['teacher_approved']=False
  with self.assertRaises(SimError) as c:apply_verified_booking_event(self.s,self.e,self.resolver)
  self.assertEqual(c.exception.code,'FORBIDDEN')
 def test_forged_booking_ownership(self):
  self.record['learner_id']='student2';self.record['booking_id']='booking2'
  with self.assertRaises(SimError):apply_verified_booking_event(self.s,self.e,self.resolver)
 def test_unverified_event(self):
  self.record['authenticated_event']=False
  with self.assertRaises(SimError):apply_verified_booking_event(self.s,self.e,self.resolver)
 def test_stale_booking_status(self):
  self.record['booking_status']='in_class'
  with self.assertRaises(SimError):apply_verified_booking_event(self.s,self.e,self.resolver)
 def test_missing_server_record(self):
  with self.assertRaises(SimError):apply_verified_booking_event(self.s,self.e,lambda _:None)
 def test_denial_never_posts_ledger(self):
  self.record['teacher_approved']=False
  with self.assertRaises(SimError):apply_verified_booking_event(self.s,self.e,self.resolver)
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0],0)
if __name__=='__main__':unittest.main()
