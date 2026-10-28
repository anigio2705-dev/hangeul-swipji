"""Ninth pass: transaction replay, recovery, and reconciliation regressions."""
import os,tempfile,unittest
from team14_persistent import MonthlyStore,SimError
from team14_booking_events import apply_booking_event
class NinthPassTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.path=os.path.join(self.tmp.name,'ledger.sqlite')
  self.s=MonthlyStore(self.path)
  self.s.create_month('month',[('lesson1','booking1',10000),('lesson2','booking2',10000),('lesson3','booking3',10000)])
 def tearDown(self):
  self.s.close();self.tmp.cleanup()
 def event(self,lesson,tx,op,action,amt=0):
  return self.s.event('month','lesson'+str(lesson),'booking'+str(lesson),tx,op,action,amt)
 def test_cross_kind_transaction_id_reuse_rejected(self):
  self.event(1,'tx','op1','refund',1000)
  with self.assertRaises(SimError) as e:self.event(2,'tx','op2','complete')
  self.assertEqual(e.exception.code,'CONFLICT')
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0],1)
 def test_rollback_and_retry_after_duplicate_tx(self):
  self.event(1,'tx','op1','complete')
  with self.assertRaises(SimError):self.event(2,'tx','op2','refund',5000)
  self.assertEqual(self.event(2,'tx2','op2','refund',5000)['state'],'partially_refunded')
 def test_recovery_after_close(self):
  self.event(1,'tx1','op1','complete')
  self.event(2,'tx2','op2','refund',2500)
  before=self.s.totals('month')
  self.s.close();self.s=MonthlyStore(self.path)
  self.assertEqual(before,self.s.totals('month'))
  self.assertEqual(self.event(1,'tx1','op1','complete')['state'],'completed')
  self.assertEqual(self.event(2,'tx2','op2','refund',2500)['state'],'partially_refunded')
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0],4)
 def test_completed_and_partial_refund_reconcile(self):
  self.event(1,'tx1','op1','complete')
  self.event(2,'tx2','op2','refund',4000)
  self.event(2,'tx3','op3','refund',6000)
  self.event(3,'tx4','op4','cancel')
  t=self.s.totals('month')
  self.assertEqual((t['gross'],t['teacher'],t['referral'],t['platform'],t['refunded'],t['pending']),(30000,8000,300,1700,20000,0))
 def test_invalid_booking_event_cannot_post(self):
  e=dict(event_id='e1',month_id='month',lesson_id='lesson1',booking_id='booking1',transaction_id='tx1',action='complete',booking_status='in_class',currency='KRW',amount_krw=0)
  with self.assertRaises(SimError):apply_booking_event(self.s,e)
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0],0)
 def test_two_distinct_event_ids_cannot_double_settle(self):
  self.event(1,'tx1','op1','complete')
  with self.assertRaises(SimError) as e:self.event(1,'tx2','op2','complete')
  self.assertEqual(e.exception.code,'INVALID_STATE')
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0],3)
if __name__=='__main__':unittest.main()
