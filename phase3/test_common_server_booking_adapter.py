import pathlib
import sqlite3
import unittest
from team11_server_booking_adapter import authenticated_booking_access

SCHEMA=pathlib.Path(__file__).with_name("schema.sql")

class ServerBookingAdapterTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        self.db.row_factory=sqlite3.Row
        self.db.executescript(SCHEMA.read_text(encoding="utf-8"))
        for uid,role,approved in (("student","learner",0),("teacher","teacher",1),("outsider","learner",0)):
            self.db.execute("INSERT INTO users(id,email,password,nickname,role,approved,referral_code,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (uid,uid+"@example.test","dummy",uid,role,approved,"ref-"+uid,0))
        self.db.execute("INSERT INTO slots(id,teacher_id,start,end) VALUES(?,?,?,?)",("slot","teacher",100,200))
        self.db.execute("INSERT INTO bookings(id,learner_id,teacher_id,slot_id,unit_id,status,price,room,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            ("booking","student","teacher","slot","unit","in_class",20000,"room",0))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def check(self,uid,action="join",bid="booking"):
        return authenticated_booking_access(self.db,uid,bid,action)

    def test_authorized_participants(self):
        self.assertTrue(self.check("student")["allowed"])
        self.assertTrue(self.check("teacher")["allowed"])

    def test_outsider_denied(self):
        self.assertEqual(self.check("outsider")["code"],"FORBIDDEN")

    def test_missing_booking_denied(self):
        self.assertEqual(self.check("student",bid="missing")["code"],"NOT_FOUND")

    def test_nonexistent_user_denied(self):
        self.assertEqual(self.check("ghost")["code"],"UNAUTHENTICATED")

    def test_revocation_immediately_denies_room(self):
        self.db.execute("UPDATE users SET approved=0 WHERE id='teacher'")
        self.db.commit()
        self.assertEqual(self.check("student")["code"],"FORBIDDEN")
        self.assertEqual(self.check("teacher")["code"],"FORBIDDEN")

    def test_role_change_denies_existing_booking(self):
        self.db.execute("UPDATE users SET role='partner',approved=1 WHERE id='student'")
        self.db.commit()
        self.assertEqual(self.check("student")["code"],"FORBIDDEN")

    def test_cancelled_booking_denies_join(self):
        self.db.execute("UPDATE bookings SET status='cancelled' WHERE id='booking'")
        self.db.commit()
        self.assertEqual(self.check("teacher")["code"],"INVALID_STATE")

    def test_completion_only_by_provider(self):
        self.assertEqual(self.check("student","complete")["code"],"FORBIDDEN")
        self.assertTrue(self.check("teacher","complete")["allowed"])

    def test_invalid_id_denied(self):
        self.assertEqual(self.check("../student")["code"],"VALIDATION_ERROR")

if __name__=="__main__":
    unittest.main()
