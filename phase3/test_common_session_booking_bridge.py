import hashlib
import pathlib
import sqlite3
import unittest
from team11_session_booking_bridge import authenticated_session_booking_access

SCHEMA=pathlib.Path(__file__).with_name("schema.sql")

class SessionBookingBridgeTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        self.db.row_factory=sqlite3.Row
        self.db.executescript(SCHEMA.read_text(encoding="utf-8"))
        for uid,role,approved in (("learner","learner",0),("teacher","teacher",1),("other","learner",0)):
            self.db.execute("INSERT INTO users(id,email,password,nickname,role,approved,referral_code,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (uid,uid+"@example.test","dummy",uid,role,approved,"ref-"+uid,0))
            self.db.execute("INSERT INTO sessions(token,user_id,expires) VALUES(?,?,?)",
                (hashlib.sha256(("session-token-"+uid).encode()).hexdigest(),uid,5000))
        self.db.execute("INSERT INTO slots(id,teacher_id,start,end) VALUES(?,?,?,?)",("slot","teacher",100,200))
        self.db.execute("INSERT INTO bookings(id,learner_id,teacher_id,slot_id,unit_id,status,price,room,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            ("booking","learner","teacher","slot","unit","in_class",20000,"room",0))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def check(self,token,action="join",now=1000):
        return authenticated_session_booking_access(self.db,token,"booking",action,now=now)

    def test_learner_and_teacher_live_sessions(self):
        self.assertTrue(self.check("session-token-learner")["allowed"])
        self.assertTrue(self.check("session-token-teacher")["allowed"])

    def test_other_member_session_denied(self):
        self.assertEqual(self.check("session-token-other")["code"],"FORBIDDEN")

    def test_expired_session_denied(self):
        self.assertEqual(self.check("session-token-learner",now=5000)["code"],"UNAUTHENTICATED")

    def test_unknown_and_malformed_token_denied(self):
        self.assertEqual(self.check("session-token-unknown")["code"],"UNAUTHENTICATED")
        self.assertEqual(self.check("")["code"],"UNAUTHENTICATED")

    def test_revoked_teacher_denied_with_valid_session(self):
        self.db.execute("UPDATE users SET approved=0 WHERE id='teacher'")
        self.db.commit()
        self.assertEqual(self.check("session-token-teacher")["code"],"FORBIDDEN")
        self.assertEqual(self.check("session-token-learner")["code"],"FORBIDDEN")

    def test_student_cannot_complete_even_with_valid_session(self):
        self.assertEqual(self.check("session-token-learner","complete")["code"],"FORBIDDEN")
        self.assertTrue(self.check("session-token-teacher","complete")["allowed"])

    def test_role_change_denies_prior_booking(self):
        self.db.execute("UPDATE users SET role='partner',approved=1 WHERE id='learner'")
        self.db.commit()
        self.assertEqual(self.check("session-token-learner")["code"],"FORBIDDEN")

    def test_cancelled_booking_denies_join(self):
        self.db.execute("UPDATE bookings SET status='cancelled' WHERE id='booking'")
        self.db.commit()
        self.assertEqual(self.check("session-token-teacher")["code"],"INVALID_STATE")

if __name__=="__main__":
    unittest.main()
