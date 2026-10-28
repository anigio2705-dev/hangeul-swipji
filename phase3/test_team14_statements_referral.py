import os,tempfile,unittest
from team14_persistent import MonthlyStore,SimError
from team14_statements import lesson_statement,month_statement
from team14_referral_eligibility import eligible_referral
class StatementsAndReferralTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=os.path.join(self.temp.name,'db.sqlite')
  self.s=MonthlyStore(self.path)
  self.s.create_month('m',[('l1','b1',101),('l2','b2',1000)])
 def tearDown(self):self.s.close();self.temp.cleanup()
 def test_statement_before_settlement(self):
  d=lesson_statement(self.s,'m','l1')
  self.assertEqual((d['pending_krw'],d['gross_krw']),(101,101))
 def test_completed_partial_refund_statement(self):
  self.s.event('m','l1','b1','tx1','op1','complete')
  self.s.event('m','l1','b1','tx2','op2','refund_completed',33)
  d=lesson_statement(self.s,'m','l1')
  self.assertEqual(d['teacher_krw']+d['referral_krw']+d['platform_krw'],68)
  self.assertEqual(d['refunded_krw'],33)
  self.assertEqual(len(d['ledger']),7)
 def test_month_totals_match(self):
  self.s.event('m','l1','b1','tx1','op1','complete')
  self.s.event('m','l2','b2','tx2','op2','cancel')
  d=month_statement(self.s,'m')
  self.assertEqual(d['totals']['pending'],0)
  self.assertEqual(len(d['lessons']),2)
 def test_statement_restart(self):
  self.s.event('m','l1','b1','tx1','op1','complete')
  before=month_statement(self.s,'m')
  self.s.close();self.s=MonthlyStore(self.path)
  self.assertEqual(before,month_statement(self.s,'m'))
 def test_unknown_lesson_rejected(self):
  with self.assertRaises(SimError):lesson_statement(self.s,'m','unknown')
 def test_referral_no_ancestor_no_reward(self):
  d=eligible_referral(10000,'student',[],(300,200))
  self.assertEqual(d['recipients'],[])
  self.assertEqual(d['teacher_krw']+d['platform_krw'],10000)
 def test_referral_only_existing_ancestor(self):
  d=eligible_referral(10000,'student',[('student','alice')],(300,200))
  self.assertEqual(d['recipients'],[dict(user_id='alice',amount_krw=300)])
  self.assertEqual(d['teacher_krw']+d['platform_krw']+300,10000)
 def test_referral_two_levels(self):
  d=eligible_referral(10000,'student',[('student','alice'),('alice','bob')],(300,200))
  self.assertEqual([x['user_id'] for x in d['recipients']],['alice','bob'])
 def test_referral_cycle_rejected(self):
  with self.assertRaises(SimError):eligible_referral(10000,'a',[('a','b'),('b','a')])
 def test_referral_duplicate_parent_rejected(self):
  with self.assertRaises(SimError):eligible_referral(10000,'a',[('a','b'),('a','c')])
if __name__=='__main__':unittest.main()
