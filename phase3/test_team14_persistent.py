import os,tempfile,unittest
from team14_persistent import MonthlyStore,SimError
class PersistentTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.path=os.path.join(self.tmp.name,'test.sqlite')
  self.s=MonthlyStore(self.path)
  self.lessons=[('l1','b1',20000),('l2','b2',20000),('l3','b3',20000),('l4','b4',20000)]
  self.s.create_month('m1',self.lessons)
 def tearDown(self): self.s.close();self.tmp.cleanup()
 def event(self,i,tx,op,action,amount=0,**kw): return self.s.event('m1','l'+str(i),'b'+str(i),tx,op,action,amount,**kw)
 def test_partial_completion_refund_cancel(self):
  self.event(1,'t1','o1','complete',booking_state='completed')
  self.event(2,'t2','o2','complete')
  self.event(3,'t3','o3','refund',5000)
  self.event(3,'t4','o4','refund',15000)
  self.event(4,'t5','o5','cancel')
  self.assertEqual(self.s.totals('m1'),dict(gross=80000,teacher=32000,referral=1200,platform=6800,refunded=40000,pending=0,real_money=False,rates_approved=False))
 def test_restart_idempotency(self):
  self.event(1,'t1','o1','complete')
  self.s.close();self.s=MonthlyStore(self.path)
  self.assertEqual(self.event(1,'t1','o1','complete')['state'],'completed')
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0],3)
 def test_duplicate_transaction(self):
  self.event(1,'t1','o1','complete')
  with self.assertRaises(SimError) as c:self.event(2,'t1','o2','complete')
  self.assertEqual(c.exception.code,'CONFLICT')
  with self.assertRaises(SimError):self.event(2,'t2','o1','complete')
 def test_booking_state_and_ids(self):
  with self.assertRaises(SimError) as c:self.s.event('m1','l1','b2','t1','o1','complete')
  self.assertEqual(c.exception.code,'NOT_FOUND')
  with self.assertRaises(SimError):self.event(1,'t1','o1','complete',booking_state='cancelled')
  self.event(1,'t2','o2','complete')
  with self.assertRaises(SimError):self.event(1,'t3','o3','refund',1000)
 def test_currency_zero_and_rates(self):
  with self.assertRaises(SimError):self.event(1,'t1','o1','refund',100,currency='USD')
  with self.assertRaises(SimError):self.event(1,'t1','o1','refund',0)
  with self.assertRaises(SimError):self.s.create_month('m2',[('l5','b5',0)])
  with self.assertRaises(SimError):self.s.create_month('m2',[('l5','b5',100)],currency='USD')
  with self.assertRaises(SimError):self.s.create_month('m2',[('l5','b5',100)],commission_bps=9900,referral_bps=300)
 def test_refund_retries_and_states(self):
  with self.assertRaises(SimError):self.event(1,'t1','o1','refund',21000)
  self.assertEqual(self.event(1,'t1','o1','refund',10000)['state'],'partially_refunded')
  self.assertEqual(self.event(1,'t1','o1','refund',10000)['state'],'partially_refunded')
  with self.assertRaises(SimError):self.event(1,'t2','o2','complete')
  self.assertEqual(self.event(1,'t3','o3','refund',10000)['state'],'refunded')
  self.assertEqual(self.s.totals('m1')['refunded'],20000)
 def test_max_and_id_validation(self):
  with self.assertRaises(SimError):self.s.create_month('bad.id',[('l5','b5',100)])
  with self.assertRaises(SimError):self.s.create_month('m2',[('l5','b5',10**15+1)])
  self.s.create_month('m2',[('l5','b5',10**15)])
  self.s.event('m2','l5','b5','tmax','omax','complete')
  self.assertEqual(self.s.totals('m2')['gross'],10**15)
 def test_create_replay(self):
  self.assertEqual(self.s.create_month('m1',self.lessons)['month_id'],'m1')
  with self.assertRaises(SimError):self.s.create_month('m1',[('x','y',100)])
if __name__=='__main__':unittest.main()
