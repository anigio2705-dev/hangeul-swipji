import os,tempfile,unittest
from team14_persistent import MonthlyStore,SimError
from team14_internal_event_consumer import consume_internal_lesson_event
class InternalEventConsumerTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.path=os.path.join(self.tmp.name,'settlement.sqlite')
  self.s=MonthlyStore(self.path)
  self.s.create_month('month1',[('lesson1','booking1',10000)])
  self.event=dict(event_id='event1',month_id='month1',lesson_id='lesson1',
      booking_id='booking1',transaction_id='tx1',action='complete',
      booking_status='completed',currency='KRW',amount_krw=0,
      learner_id='student1',teacher_id='teacher1')
  self.record=dict(booking_id='booking1',month_id='month1',lesson_id='lesson1',
      learner_id='student1',teacher_id='teacher1',teacher_approved=True,
      booking_status='completed',authenticated_event=True)
 def tearDown(self):self.s.close();self.tmp.cleanup()
 def consume(self):
  return consume_internal_lesson_event(self.s,'event1',
      lambda eid:self.event,lambda bid:self.record)
 def test_verified_completion_posts_once(self):
  self.assertEqual(self.consume()['state'],'completed')
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0],3)
 def test_duplicate_delivery_is_idempotent(self):
  self.consume();self.consume()
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0],3)
 def test_restart_replay(self):
  self.consume();before=self.s.totals('month1')
  self.s.close();self.s=MonthlyStore(self.path)
  self.consume();self.assertEqual(self.s.totals('month1'),before)
 def test_teacher_not_approved(self):
  self.record['teacher_approved']=False
  with self.assertRaises(SimError):self.consume()
 def test_student_mismatch(self):
  self.event['learner_id']='other'
  with self.assertRaises(SimError):self.consume()
 def test_teacher_mismatch(self):
  self.event['teacher_id']='other'
  with self.assertRaises(SimError):self.consume()
 def test_unverified_source(self):
  self.record['authenticated_event']=False
  with self.assertRaises(SimError):self.consume()
 def test_missing_callbacks(self):
  with self.assertRaises(SimError):
   consume_internal_lesson_event(self.s,'event1',None,lambda bid:self.record)
 def test_forged_event_id(self):
  self.event['event_id']='different'
  with self.assertRaises(SimError):self.consume()
 def test_cancelled_booking_blocked(self):
  self.record['booking_status']='cancelled'
  with self.assertRaises(SimError):self.consume()
if __name__=='__main__':unittest.main()
