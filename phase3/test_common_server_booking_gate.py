"""Regression for the actual server.Handler.booking access gate."""
import pathlib
import sqlite3
import unittest

from server import Handler, Error

SCHEMA=pathlib.Path(__file__).with_name("schema.sql")

class LiveBookingHelperTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        self.db.row_factory=sqlite3.Row
        self.db.executescript(SCHEMA.read_text(encoding="utf-8"))
        for uid,role,approved in (("student","learner",0),("teacher","teacher",1),("other","learner",0)):
            self.db.execute("INSERT INTO users(id,email,password,nickname,role,approved,referral_code,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (uid,uid+"@example.test","dummy",uid,role,approved,"ref-"+uid,0))
        self.db.execute("INSERT INTO slots(id,teacher_id,start,end) VALUES(?,?,?,?)",("slot","teacher",100,200))
        self.db.execute("INSERT INTO bookings(id,learner_id,teacher_id,slot_id,unit_id,status,price,room,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            ("booking","student","teacher","slot","unit","reserved",20000,"room",0))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def access(self,uid):
        user=self.db.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone()
        return Handler.booking(None,self.db,"booking",user)

    def test_existing_approved_participants_access(self):
        self.assertEqual(self.access("student")["id"],"booking")
        self.assertEqual(self.access("teacher")["id"],"booking")

    def test_outsider_rejected_at_actual_server_gate(self):
        with self.assertRaises(Error) as err:
            self.access("other")
        self.assertEqual(err.exception.status,403)

    def test_revoked_provider_denies_existing_booking(self):
        self.db.execute("UPDATE users SET approved=0 WHERE id='teacher'")
        self.db.commit()
        for uid in ("student","teacher"):
            with self.assertRaises(Error) as err:
                self.access(uid)
            self.assertEqual(err.exception.status,403)

    def test_role_changed_student_denied(self):
        self.db.execute("UPDATE users SET role='partner',approved=1 WHERE id='student'")
        self.db.commit()
        with self.assertRaises(Error) as err:
            self.access("student")
        self.assertEqual(err.exception.status,403)

if __name__=="__main__":
    unittest.main()
