import os,tempfile,unittest
from team14_persistent import MonthlyStore,SimError
class CompletedRefundTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=os.path.join(self.tmp.name,'db.sqlite')
  self.s=MonthlyStore(self.path)
  self.s.create_month('m',[('l','b',101),('l2','b2',20000)])
  self.s.event('m','l','b','t1','o1','complete')
 def tearDown(self):self.s.close();self.tmp.cleanup()
 def refund(self,tx,op,n):
  return self.s.event('m','l','b',tx,op,'refund_completed',n)
 def test_partial_then_full_and_conservation(self):
  self.assertEqual(self.refund('t2','o2',33)['state'],'completed_partially_refunded')
  self.assertEqual(self.refund('t3','o3',68)['state'],'refunded')
  t=self.s.totals('m')
  self.assertEqual((t['teacher'],t['referral'],t['platform'],t['refunded'],t['pending']),(0,0,0,101,20000))
 def test_replay_and_restart(self):
  self.refund('t2','o2',33);before=self.s.totals('m')
  self.s.close();self.s=MonthlyStore(self.path)
  self.assertEqual(self.refund('t2','o2',33)['state'],'completed_partially_refunded')
  self.assertEqual(before,self.s.totals('m'))
 def test_over_refund_rejected(self):
  with self.assertRaises(SimError):self.refund('t2','o2',102)
 def test_reused_transaction_rejected(self):
  with self.assertRaises(SimError):self.refund('t1','o2',33)
 def test_duplicate_operation_conflict(self):
  self.refund('t2','o2',33)
  with self.assertRaises(SimError):self.refund('t3','o2',33)
 def test_partial_net_allocation(self):
  self.refund('t2','o2',33)
  t=self.s.totals('m')
  self.assertEqual(t['teacher']+t['referral']+t['platform'],68)
  self.assertEqual(t['pending'],20000)
 def test_reserved_completed_refund_rejected(self):
  with self.assertRaises(SimError):self.s.event('m','l2','b2','t2','o2','refund_completed',100)
if __name__=='__main__':unittest.main()
