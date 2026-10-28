import os,sqlite3,tempfile,unittest
from team14_persistent import MonthlyStore,SimError
from team14_referral_store import ReferralStore
from team14_server_db_wiring import settle_from_server_db
class ServerDbWiringTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.server=os.path.join(self.tmp.name,'server.sqlite')
  self.sp=os.path.join(self.tmp.name,'settle.sqlite')
  self.rp=os.path.join(self.tmp.name,'referral.sqlite')
  with sqlite3.connect(self.server) as db:
   db.executescript("""CREATE TABLE users(id TEXT PRIMARY KEY,role TEXT,approved INTEGER,referred_by TEXT);
    CREATE TABLE bookings(id TEXT PRIMARY KEY,learner_id TEXT,teacher_id TEXT,status TEXT);""")
   db.executemany('INSERT INTO users VALUES(?,?,?,?)',[
    ('student','learner',0,'parent'),('parent','learner',0,None),
    ('teacher','teacher',1,None)])
   db.execute("INSERT INTO bookings VALUES('booking','student','teacher','completed')")
  self.s=MonthlyStore(self.sp);self.r=ReferralStore(self.rp)
  self.s.create_month('month',[('lesson','booking',10000)])
  self.events={'ev':dict(event_id='ev',month_id='month',lesson_id='lesson',
      booking_id='booking',transaction_id='tx',action='complete',
      booking_status='completed',currency='KRW',amount_krw=0,
      learner_id='student',teacher_id='teacher')}
 def tearDown(self):self.s.close();self.r.close();self.tmp.cleanup()
 def run_event(self,eid='ev'):
  return settle_from_server_db(self.s,self.r,self.server,eid,lambda i:self.events.get(i))
 def test_real_sqlite_booking_to_ledger_and_referral(self):
  result=self.run_event()
  self.assertEqual(result['settlement']['state'],'completed')
  self.assertEqual(result['referral_award']['recipients'][0]['user_id'],'parent')
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0],3)
 def test_repeated_server_event(self):
  self.run_event();self.run_event()
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0],3)
  self.assertEqual(self.r.db.execute('SELECT COUNT(*) FROM referral_awards').fetchone()[0],1)
 def test_restart_all_databases(self):
  self.run_event();self.s.close();self.r.close()
  self.s=MonthlyStore(self.sp);self.r=ReferralStore(self.rp)
  self.run_event()
  self.assertEqual(self.r.db.execute('SELECT COUNT(*) FROM referral_awards').fetchone()[0],1)
 def test_teacher_approval_revoked_in_real_db(self):
  with sqlite3.connect(self.server) as db:
   db.execute("UPDATE users SET approved=0 WHERE id='teacher'")
  with self.assertRaises(SimError):self.run_event()
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0],0)
 def test_booking_cancelled_in_real_db(self):
  with sqlite3.connect(self.server) as db:
   db.execute("UPDATE bookings SET status='cancelled' WHERE id='booking'")
  with self.assertRaises(SimError):self.run_event()
 def test_student_mismatch(self):
  self.events['ev']['learner_id']='other'
  with self.assertRaises(SimError):self.run_event()
 def test_refund_from_real_db(self):
  self.run_event()
  with sqlite3.connect(self.server) as db:
   db.execute("UPDATE bookings SET status='refunded' WHERE id='booking'")
  self.events['refund']=dict(self.events['ev'],event_id='refund',transaction_id='txrefund',
    action='refund_completed',booking_status='refunded',amount_krw=4000)
  self.run_event('refund')
  self.assertEqual(self.s.totals('month')['refunded'],4000)
 def test_missing_authenticated_event(self):
  with self.assertRaises(SimError):
   settle_from_server_db(self.s,self.r,self.server,'ev',None)
if __name__=='__main__':unittest.main()
