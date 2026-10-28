"""Actual GET /api/bookings route authorization regression."""
import pathlib
import sqlite3
import unittest
from server import Handler

SCHEMA=pathlib.Path(__file__).with_name("schema.sql")

class BookingListRouteTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        self.db.row_factory=sqlite3.Row
        self.db.executescript(SCHEMA.read_text(encoding="utf-8"))
        for uid,role,approved in (("student","learner",0),("teacher","teacher",1)):
            self.db.execute("INSERT INTO users(id,email,password,nickname,role,approved,referral_code,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (uid,uid+"@example.test","dummy",uid,role,approved,"ref-"+uid,0))
        self.db.execute("INSERT INTO slots(id,teacher_id,start,end) VALUES(?,?,?,?)",("slot","teacher",100,200))
        self.db.execute("INSERT INTO bookings(id,learner_id,teacher_id,slot_id,unit_id,status,price,room,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            ("booking","student","teacher","slot","unit","reserved",20000,"room",0))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def list_for(self,uid):
        handler=object.__new__(Handler)
        handler.command="GET"
        handler.user=lambda db: db.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone()
        result,_=handler.route(self.db,"/api/bookings",{}, {})
        return result["bookings"]

    def test_active_provider_learner_can_list(self):
        self.assertEqual(len(self.list_for("student")),1)
        self.assertEqual(len(self.list_for("teacher")),1)

    def test_provider_revocation_removes_booking_from_both_lists(self):
        self.db.execute("UPDATE users SET approved=0 WHERE id='teacher'")
        self.db.commit()
        self.assertEqual(self.list_for("student"),[])
        self.assertEqual(self.list_for("teacher"),[])

    def test_student_role_change_hides_prior_booking(self):
        self.db.execute("UPDATE users SET role='partner',approved=1 WHERE id='student'")
        self.db.commit()
        self.assertEqual(self.list_for("student"),[])

if __name__=="__main__":
    unittest.main()
