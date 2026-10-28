import os,sqlite3,tempfile,unittest
from team14_persistent import SimError
from team14_team11_db_adapter import read_server_booking,read_server_referral_parent
class RealServerDbAdapterTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.path=os.path.join(self.tmp.name,'server.sqlite')
  with sqlite3.connect(self.path) as db:
   db.executescript("""CREATE TABLE users(id TEXT PRIMARY KEY,role TEXT,approved INTEGER,referred_by TEXT);
   CREATE TABLE bookings(id TEXT PRIMARY KEY,learner_id TEXT,teacher_id TEXT,status TEXT);""")
   db.executemany('INSERT INTO users VALUES(?,?,?,?)',[
    ('student','learner',0,'referrer'),('referrer','learner',0,None),
    ('teacher','teacher',1,None),('badteacher','teacher',0,None)])
   db.execute("INSERT INTO bookings VALUES('booking','student','teacher','completed')")
 def tearDown(self):self.tmp.cleanup()
 def test_reads_actual_booking_and_roles(self):
  r=read_server_booking(self.path,'booking','month','lesson',True)
  self.assertEqual(r['learner_id'],'student')
  self.assertEqual(r['teacher_id'],'teacher')
  self.assertTrue(r['teacher_approved'])
  self.assertTrue(r['authenticated_event'])
 def test_referral_comes_from_server_users(self):
  self.assertEqual(read_server_referral_parent(self.path,'student'),'referrer')
 def test_no_referrer(self):
  self.assertIsNone(read_server_referral_parent(self.path,'teacher'))
 def test_unapproved_teacher(self):
  with sqlite3.connect(self.path) as db:
   db.execute("UPDATE users SET approved=0 WHERE id='teacher'")
  self.assertFalse(read_server_booking(self.path,'booking','month','lesson')['teacher_approved'])
 def test_booking_status_follows_server_db(self):
  with sqlite3.connect(self.path) as db:
   db.execute("UPDATE bookings SET status='cancelled' WHERE id='booking'")
  self.assertEqual(read_server_booking(self.path,'booking','month','lesson')['booking_status'],'cancelled')
 def test_missing_booking(self):
  with self.assertRaises(SimError):read_server_booking(self.path,'other','month','lesson')
 def test_missing_student(self):
  with self.assertRaises(SimError):read_server_referral_parent(self.path,'other')
 def test_no_client_authentication_claim_by_default(self):
  self.assertFalse(read_server_booking(self.path,'booking','month','lesson')['authenticated_event'])
 def test_restart_read(self):
  self.assertEqual(read_server_booking(self.path,'booking','month','lesson')['booking_id'],'booking')
if __name__=='__main__':unittest.main()
