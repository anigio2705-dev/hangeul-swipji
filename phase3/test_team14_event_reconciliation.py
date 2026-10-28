import os,tempfile,unittest
from team14_persistent import MonthlyStore,SimError
from team14_referral_store import ReferralStore
from team14_event_reconciliation import reconcile_events
class ReconcileTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.sp=os.path.join(self.tmp.name,'settle.db')
  self.rp=os.path.join(self.tmp.name,'referral.db')
  self.s=MonthlyStore(self.sp);self.r=ReferralStore(self.rp)
  self.s.create_month('m',[('l','b',10000)])
  self.events={'e1':dict(event_id='e1',month_id='m',lesson_id='l',booking_id='b',
      transaction_id='t1',action='complete',booking_status='completed',
      currency='KRW',amount_krw=0,learner_id='student',teacher_id='teacher')}
  self.booking=dict(booking_id='b',month_id='m',lesson_id='l',learner_id='student',
      teacher_id='teacher',teacher_approved=True,booking_status='completed',
      authenticated_event=True)
 def tearDown(self):self.s.close();self.r.close();self.tmp.cleanup()
 def run_batch(self,ids):
  return reconcile_events(self.s,self.r,ids,lambda e:self.events.get(e),
      lambda b:self.booking,lambda student:'parent')
 def test_reconcile_posts_three_party_ledger_and_award(self):
  self.assertEqual(self.run_batch(['e1'])[0]['ledger_entries'],3)
  self.assertEqual(len(self.r.awards_for_lesson('l')['recipients']),1)
 def test_replay_is_idempotent(self):
  self.run_batch(['e1']);self.run_batch(['e1'])
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0],3)
  self.assertEqual(self.r.db.execute('SELECT COUNT(*) FROM referral_awards').fetchone()[0],1)
 def test_restart_replay(self):
  self.run_batch(['e1']);self.s.close();self.r.close()
  self.s=MonthlyStore(self.sp);self.r=ReferralStore(self.rp)
  self.assertEqual(self.run_batch(['e1'])[0]['ledger_entries'],3)
 def test_refund_and_replay(self):
  self.run_batch(['e1'])
  self.events['e2']=dict(self.events['e1'],event_id='e2',transaction_id='t2',
     action='refund_completed',booking_status='refunded',amount_krw=4000)
  self.booking['booking_status']='refunded'
  self.assertEqual(self.run_batch(['e2'])[0]['refunded_krw'],4000)
  self.assertEqual(self.run_batch(['e2'])[0]['refunded_krw'],4000)
 def test_duplicate_batch_rejected(self):
  with self.assertRaises(SimError):self.run_batch(['e1','e1'])
 def test_unknown_event_rejected(self):
  with self.assertRaises(SimError):self.run_batch(['missing'])
 def test_unapproved_teacher_rejected(self):
  self.booking['teacher_approved']=False
  with self.assertRaises(SimError):self.run_batch(['e1'])
 def test_forged_student_rejected(self):
  self.events['e1']['learner_id']='other'
  with self.assertRaises(SimError):self.run_batch(['e1'])
 def test_reconciliation_after_referral_failure(self):
  original=self.r.award
  def fail(*a,**kw):raise RuntimeError('injected failure')
  self.r.award=fail
  with self.assertRaises(RuntimeError):self.run_batch(['e1'])
  self.r.award=original
  self.run_batch(['e1'])
  self.assertEqual(self.r.db.execute('SELECT COUNT(*) FROM referral_awards').fetchone()[0],1)
if __name__=='__main__':unittest.main()
