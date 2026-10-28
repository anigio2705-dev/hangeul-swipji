"""Regression for persisted booking history and current provider approval."""
import pathlib
import sqlite3
import unittest
from team11_server_booking_adapter import authenticated_booking_access

SCHEMA=pathlib.Path(__file__).with_name("schema.sql")

class BookingStateAccessTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        self.db.row_factory=sqlite3.Row
        self.db.executescript(SCHEMA.read_text(encoding="utf-8"))
        for uid,role,approved in (("student","learner",0),("teacher","teacher",1)):
            self.db.execute("INSERT INTO users(id,email,password,nickname,role,approved,referral_code,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (uid,uid+"@example.test","dummy",uid,role,approved,"ref-"+uid,0))
        self.db.execute("INSERT INTO slots(id,teacher_id,start,end) VALUES(?,?,?,?)",("slot","teacher",100,200))
        self.db.execute("INSERT INTO bookings(id,learner_id,teacher_id,slot_id,unit_id,status,price,room,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            ("booking","student","teacher","slot","unit","test_settled",20000,"room",0))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_settled_history_remains_visible(self):
        self.assertTrue(authenticated_booking_access(self.db,"student","booking","view")["allowed"])

    def test_settled_room_join_denied(self):
        self.assertEqual(authenticated_booking_access(self.db,"teacher","booking","join")["code"],"INVALID_STATE")

    def test_revoked_provider_denied_for_old_booking(self):
        self.db.execute("UPDATE users SET approved=0 WHERE id='teacher'")
        self.db.commit()
        self.assertEqual(authenticated_booking_access(self.db,"student","booking","view")["code"],"FORBIDDEN")

if __name__=="__main__":
    unittest.main()
