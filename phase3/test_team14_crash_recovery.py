"""Failure injection against real Team14 SQLite transactions and Team13 verified event."""
import os,tempfile,sqlite3,unittest
import team14_persistent as persistent
import team14_recovery as recovery
from team14_persistent import MonthlyStore,SimError
from team14_referral_store import ReferralStore
from team14_refund_workflow import request_refund,decide_refund,apply_approved_refund
from team14_statements import lesson_statement

class RecoveryCrashTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.sp=os.path.join(self.t.name,'s.db');self.rp=os.path.join(self.t.name,'r.db')
  self.s=MonthlyStore(self.sp);self.r=ReferralStore(self.rp)
  self.s.create_month('month',[('lesson','booking',10000)])
  self.event=dict(event_id='event',booking_id='booking',month_id='month',lesson_id='lesson',
                  transaction_id='event',action='complete',booking_status='completed',
                  currency='KRW',amount_krw=0,learner_id='student',teacher_id='teacher')
  self.booking=dict(booking_id='booking',month_id='month',lesson_id='lesson',
                    learner_id='student',teacher_id='teacher',teacher_approved=True,
                    authenticated_event=True,booking_status='completed')
  self.server=sqlite3.connect(':memory:');self.server.row_factory=sqlite3.Row
  self.server.executescript("""CREATE TABLE bookings(id TEXT PRIMARY KEY,learner_id TEXT,teacher_id TEXT,status TEXT,price INTEGER);
     INSERT INTO bookings VALUES('booking','student','teacher','completed',10000);""")
 def tearDown(self):
  persistent.FAULT_HOOK=None;recovery.FAULT_HOOK=None
  self.s.close();self.r.close();self.server.close();self.t.cleanup()
 def run_event(self):
  return recovery.settle_recoverably(self.s,self.r,'event',
          lambda event_id:self.event if event_id=='event' else None,
          lambda booking_id:self.booking,
          lambda student:'parent')
 def restart(self):
  self.s.close();self.r.close();self.s=MonthlyStore(self.sp);self.r=ReferralStore(self.rp)
 def balances(self):
  x=lesson_statement(self.s,'month','lesson')
  return x['teacher_krw'],x['referral_krw'],x['platform_krw'],len(x['ledger'])
 def test_failures_at_every_settlement_boundary(self):
  for point in ('after_event_received','before_settlement','before_ledger',
       'after_teacher_accrual','after_referral_accrual','after_platform_remainder',
       'before_operation_commit','after_referral_award','before_settlement_done'):
   with self.subTest(point=point):
    self.s.close();self.r.close()
    os.remove(self.sp);os.remove(self.rp)
    self.s=MonthlyStore(self.sp);self.r=ReferralStore(self.rp)
    self.s.create_month('month',[('lesson','booking',10000)])
    def crash(here):
     if here==point:raise RuntimeError('injected '+point)
    if point.startswith('after_') and point not in ('after_event_received','after_referral_award'):
     persistent.FAULT_HOOK=crash
    elif point in ('before_ledger','before_operation_commit'):
     persistent.FAULT_HOOK=crash
    else:recovery.FAULT_HOOK=crash
    with self.assertRaises(RuntimeError):self.run_event()
    persistent.FAULT_HOOK=None;recovery.FAULT_HOOK=None
    self.restart()
    recovery.recover_prepared(self.s,self.r,lambda i:self.event,
                            lambda i:self.booking,lambda i:'parent')
    self.run_event()
    self.assertEqual((8000,300,1700,3),self.balances())
    self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM operations WHERE id=?',('event',)).fetchone()[0],1)
    self.assertEqual(self.r.db.execute('SELECT COUNT(*) FROM referral_awards').fetchone()[0],1)
    self.assertEqual(recovery.recovery_status(self.s,'event')['status'],'settled')
 def test_refund_request_decision_and_atomic_failure(self):
  self.run_event()
  original=request_refund(self.server,self.s,'booking','refund1','student',4000)
  self.assertEqual(original['state'],'requested')
  self.assertEqual(request_refund(self.server,self.s,'booking','refund1','student',4000)['state'],'requested')
  with self.assertRaises(SimError):request_refund(self.server,self.s,'booking','refund1','student',5000)
  with self.assertRaises(SimError):request_refund(self.server,self.s,'booking','other','stranger',1000)
  with self.assertRaises(SimError):decide_refund(self.s,'refund1','approved','stranger')
  self.assertEqual(decide_refund(self.s,'refund1','approved','test_reviewer')['state'],'approved')
  for point in ('after_refund_reversal','after_teacher_reversal','after_referral_reversal',
                'after_platform_reversal','before_refund_commit'):
   def crash(here):
    if here==point:raise RuntimeError(point)
   persistent.FAULT_HOOK=crash
   with self.assertRaises(RuntimeError):apply_approved_refund(self.server,self.s,'refund1')
   persistent.FAULT_HOOK=None
   self.restart()
   self.assertEqual(0,lesson_statement(self.s,'month','lesson')['refunded_krw'])
   self.assertEqual(self.s.db.execute('SELECT state FROM refund_requests WHERE request_id=?',('refund1',)).fetchone()[0],'approved')
  applied=apply_approved_refund(self.server,self.s,'refund1')
  self.assertEqual(applied,apply_approved_refund(self.server,self.s,'refund1'))
  self.assertEqual(4000,lesson_statement(self.s,'month','lesson')['refunded_krw'])
  self.assertEqual(len(lesson_statement(self.s,'month','lesson')['ledger']),7)
  self.assertEqual(self.s.db.execute('SELECT state FROM refund_requests WHERE request_id=?',('refund1',)).fetchone()[0],'applied')
  self.restart()
  self.assertEqual(applied,apply_approved_refund(self.server,self.s,'refund1'))
  with self.assertRaises(SimError):decide_refund(self.s,'refund1','cancelled','test_reviewer')
 def test_reject_and_cancel_are_terminal(self):
  self.run_event()  # refund requests require a completed mock settlement
  for suffix,choice in (('reject','rejected'),('cancel','cancelled')):
   rid='refund_'+suffix
   request_refund(self.server,self.s,'booking',rid,'student',1000)
   self.assertEqual(decide_refund(self.s,rid,choice,'test_reviewer')['state'],choice)
   with self.assertRaises(SimError):apply_approved_refund(self.server,self.s,rid)
   with self.assertRaises(SimError):decide_refund(self.s,rid,'approved','test_reviewer')

if __name__=='__main__':unittest.main(verbosity=2)
