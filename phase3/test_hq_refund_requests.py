"""Prevent over-requested simulated refunds without losing replay safety."""
import sqlite3,unittest
from team14_persistent import MonthlyStore,SimError
from team14_refund_workflow import request_refund,decide_refund,apply_approved_refund

class RefundRequestBalanceTests(unittest.TestCase):
    def setUp(self):
        self.server=sqlite3.connect(':memory:')
        self.server.row_factory=sqlite3.Row
        self.server.execute('CREATE TABLE bookings(id TEXT PRIMARY KEY,learner_id TEXT,teacher_id TEXT,price INTEGER,status TEXT)')
        self.server.execute("INSERT INTO bookings VALUES('booking','student','teacher',100,'completed')")
        self.store=MonthlyStore()
        self.store.create_month('month',[('lesson','booking',100)])
        self.store.event('month','lesson','booking','settle','settle-op','complete')
    def tearDown(self):self.store.close();self.server.close()
    def request(self,request_id,amount):return request_refund(self.server,self.store,'booking',request_id,'student',amount)
    def test_reserve_balance_and_preserve_idempotency(self):
        first=self.request('refund-1',60)
        self.assertEqual(first,self.request('refund-1',60))
        with self.assertRaises(SimError) as e:self.request('refund-2',50)
        self.assertEqual('INVALID_STATE',e.exception.code)
        self.assertEqual('requested',self.request('refund-2',40)['state'])
        for req in ('refund-1','refund-2'):
            decide_refund(self.store,req,'approved','test_reviewer')
            apply_approved_refund(self.server,self.store,req)
        self.assertEqual(100,self.store.db.execute("SELECT refunded FROM lessons WHERE id='lesson'").fetchone()[0])
        self.assertEqual('applied',self.request('refund-1',60)['state'])
        with self.assertRaises(SimError):self.request('refund-3',1)
    def test_rejection_releases_reservation(self):
        self.request('refund-1',70)
        decide_refund(self.store,'refund-1','rejected','test_reviewer')
        self.assertEqual('requested',self.request('refund-2',100)['state'])
    def test_wrong_learner_cannot_reserve(self):
        with self.assertRaises(SimError) as e:
            request_refund(self.server,self.store,'booking','other','teacher',100)
        self.assertEqual('FORBIDDEN',e.exception.code)
        self.assertEqual(0,self.store.db.execute('SELECT count(*) FROM refund_requests').fetchone()[0])

if __name__=='__main__':unittest.main()
