"""Exercise Team14 against the repository's real phase3 SQL schema (not mocks)."""
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from team14_persistent import MonthlyStore,SimError
from team14_referral_store import ReferralStore
from team14_server_db_wiring import settle_from_server_db
from team14_statements import month_statement

class ActualSchemaIntegration(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.server=os.path.join(self.tmp.name,'server.db')
  self.s=MonthlyStore(os.path.join(self.tmp.name,'settlement.db'))
  self.r=ReferralStore(os.path.join(self.tmp.name,'referral.db'))
  schema=Path(__file__).with_name('schema.sql').read_text()
  with sqlite3.connect(self.server) as db:
   db.executescript(schema)
   for uid,role,approved,parent in (
      ('parent','learner',0,None),('student','learner',0,'parent'),
      ('teacher','teacher',1,None)):
    db.execute("""INSERT INTO users
      (id,email,password,nickname,role,approved,referral_code,referred_by,created_at)
      VALUES(?,?,?,?,?,?,?,?,?)""",
      (uid,uid+'@test.invalid','test-only',uid,role,approved,'code_'+uid,parent,1))
   db.execute("INSERT INTO slots(id,teacher_id,start,end) VALUES('slot','teacher',100,200)")
   db.execute("""INSERT INTO bookings
      (id,learner_id,teacher_id,slot_id,unit_id,status,price,room,created_at)
      VALUES('booking','student','teacher','slot','unit','completed',10000,'room',1)""")
  self.s.create_month('month',[('lesson','booking',10000)])
  self.events={'complete':dict(event_id='complete',month_id='month',
     lesson_id='lesson',booking_id='booking',transaction_id='tx_complete',
     action='complete',booking_status='completed',currency='KRW',
     amount_krw=0,learner_id='student',teacher_id='teacher')}
 def tearDown(self):
  self.s.close();self.r.close();self.tmp.cleanup()
 def deliver(self,eid):
  return settle_from_server_db(self.s,self.r,self.server,eid,lambda key:self.events.get(key))
 def test_complete_referral_partial_refund_replay_and_restart(self):
  self.deliver('complete');self.deliver('complete')
  self.assertEqual(self.r.awards_for_lesson('lesson')['recipients'][0]['user_id'],'parent')
  with sqlite3.connect(self.server) as db:
   db.execute("UPDATE bookings SET status='refunded' WHERE id='booking'")
  self.events['refund']=dict(self.events['complete'],event_id='refund',
      transaction_id='tx_refund',action='refund_completed',
      booking_status='refunded',amount_krw=4000)
  self.deliver('refund');self.deliver('refund')
  self.assertEqual(month_statement(self.s,'month')['totals']['refunded'],4000)
  self.s.close();self.r.close()
  self.s=MonthlyStore(os.path.join(self.tmp.name,'settlement.db'))
  self.r=ReferralStore(os.path.join(self.tmp.name,'referral.db'))
  self.deliver('refund')
  self.assertEqual(month_statement(self.s,'month')['totals']['refunded'],4000)
 def test_forged_learner_rejected_with_real_schema(self):
  self.events['complete']['learner_id']='intruder'
  with self.assertRaises(SimError):self.deliver('complete')
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0],0)
 def test_server_booking_price_mismatch_rejected_with_real_schema(self):
  with sqlite3.connect(self.server) as db:
   db.execute("UPDATE bookings SET price=15000 WHERE id='booking'")
  with self.assertRaises(SimError):self.deliver('complete')
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0],0)
 def test_teacher_approval_revoked_with_real_schema(self):
  with sqlite3.connect(self.server) as db:
   db.execute("UPDATE users SET approved=0 WHERE id='teacher'")
  with self.assertRaises(SimError):self.deliver('complete')
if __name__=='__main__':unittest.main()
