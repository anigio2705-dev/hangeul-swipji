import os,tempfile,unittest
from team14_persistent import MonthlyStore,SimError
from team14_referral_store import ReferralStore
from team14_settlement_coordinator import settle_with_referral
from team14_statements import month_statement
class CoordinatorTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.settlement_path=os.path.join(self.tmp.name,'settlement.db')
  self.referral_path=os.path.join(self.tmp.name,'referrals.db')
  self.s=MonthlyStore(self.settlement_path)
  self.r=ReferralStore(self.referral_path)
  self.s.create_month('month1',[('lesson1','booking1',10000)])
  self.event=dict(event_id='ev1',month_id='month1',lesson_id='lesson1',
     booking_id='booking1',transaction_id='tx1',action='complete',
     booking_status='completed',currency='KRW',amount_krw=0,
     learner_id='student1',teacher_id='teacher1')
  self.record=dict(booking_id='booking1',month_id='month1',lesson_id='lesson1',
     learner_id='student1',teacher_id='teacher1',teacher_approved=True,
     booking_status='completed',authenticated_event=True)
 def tearDown(self):self.s.close();self.r.close();self.tmp.cleanup()
 def run_event(self,parent='referrer1'):
  return settle_with_referral(self.s,self.r,self.event['event_id'],
      lambda eid:self.event,lambda bid:self.record,lambda student:parent)
 def test_completion_and_referral(self):
  result=self.run_event()
  self.assertEqual(result['settlement']['state'],'completed')
  self.assertEqual(result['referral_award']['recipients'][0]['user_id'],'referrer1')
  self.assertEqual(month_statement(self.s,'month1')['totals']['gross'],10000)
 def test_duplicate_completion(self):
  self.run_event();self.run_event()
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0],3)
  self.assertEqual(self.r.db.execute('SELECT COUNT(*) FROM referral_awards').fetchone()[0],1)
 def test_restart_replay(self):
  self.run_event()
  self.s.close();self.r.close()
  self.s=MonthlyStore(self.settlement_path);self.r=ReferralStore(self.referral_path)
  self.run_event()
  self.assertEqual(self.r.db.execute('SELECT COUNT(*) FROM referral_awards').fetchone()[0],1)
 def test_missing_parent(self):
  self.assertEqual(self.run_event(None)['referral_award']['recipients'],[])
 def test_untrusted_referral_lookup(self):
  with self.assertRaises(SimError):
   settle_with_referral(self.s,self.r,'ev1',lambda eid:self.event,
     lambda bid:self.record,None)
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0],0)
 def test_forged_student(self):
  self.event['learner_id']='other'
  with self.assertRaises(SimError):self.run_event()
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0],0)
 def test_unapproved_teacher(self):
  self.record['teacher_approved']=False
  with self.assertRaises(SimError):self.run_event()
 def test_refund_after_completion(self):
  self.run_event()
  self.event.update(event_id='ev2',transaction_id='tx2',action='refund_completed',
                    booking_status='refunded',amount_krw=4000)
  self.record['booking_status']='refunded'
  result=self.run_event()
  self.assertIsNone(result['referral_award'])
  self.assertEqual(month_statement(self.s,'month1')['totals']['refunded'],4000)
 def test_referral_parent_change_rejected(self):
  self.run_event()
  with self.assertRaises(SimError):self.run_event('other_parent')
if __name__=='__main__':unittest.main()
