"""Real local HTTP + SQLite integration: session, booking visibility, revocation.

Uses a loopback ephemeral port and isolated temporary DB; never production.
"""
import hashlib
import http.client
import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer

import server as phase3

class BookingHttpIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.old_path=phase3.DB_PATH
        phase3.DB_PATH=os.path.join(cls.tmp.name,"isolated.sqlite3")
        phase3.init_db()
        with phase3.connect() as db:
            for uid,role,approved in (("student","learner",0),("teacher","teacher",1),("outsider","learner",0)):
                db.execute("INSERT INTO users(id,email,password,nickname,role,approved,referral_code,created_at) VALUES(?,?,?,?,?,?,?,?)",
                    (uid,uid+"@example.test","dummy",uid,role,approved,"ref-"+uid,time.time()))
                db.execute("INSERT INTO sessions(token,user_id,expires) VALUES(?,?,?)",
                    (hashlib.sha256(("session-token-"+uid).encode()).hexdigest(),uid,time.time()+3600))
            db.execute("INSERT INTO slots(id,teacher_id,start,end) VALUES(?,?,?,?)",("slot","teacher",time.time()+600,time.time()+2400))
            db.execute("INSERT INTO bookings(id,learner_id,teacher_id,slot_id,unit_id,status,price,room,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                ("booking","student","teacher","slot","unit","reserved",20000,"private-room",time.time()))
        cls.http=ThreadingHTTPServer(("127.0.0.1",0),phase3.Handler)
        cls.http.failures={}
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join(timeout=5)
        phase3.DB_PATH=cls.old_path
        cls.tmp.cleanup()

    def setUp(self):
        # unittest runs methods alphabetically. Restore only the test fixtures
        # mutated by prior cases; never relax HTTP status/security assertions.
        with phase3.connect() as db:
            db.execute("UPDATE sessions SET expires=? WHERE user_id IN ('student','teacher','outsider')", (time.time()+3600,))
            db.execute("UPDATE users SET approved=1 WHERE id='teacher'")
            db.execute("UPDATE users SET role='learner' WHERE id IN ('student','outsider')")

    def request(self,uid=None,path="/api/bookings"):
        connection=http.client.HTTPConnection("127.0.0.1",self.http.server_port,timeout=5)
        headers={"Host":"127.0.0.1:"+str(self.http.server_port)}
        if uid: headers["Cookie"]="hs3=session-token-"+uid
        try:
            connection.request("GET",path,headers=headers)
            response=connection.getresponse()
            return response.status,json.loads(response.read())
        finally:
            connection.close()

    def test_student_sees_only_own_booking(self):
        status,body=self.request("student")
        self.assertEqual(status,200)
        self.assertEqual(len(body["bookings"]),1)
        self.assertNotIn("room",body["bookings"][0])

    def test_outsider_cannot_list_other_booking(self):
        status,body=self.request("outsider")
        self.assertEqual(status,200)
        self.assertEqual(body["bookings"],[])

    def test_missing_and_expired_sessions(self):
        self.assertEqual(self.request()[0],401)
        with phase3.connect() as db:
            db.execute("UPDATE sessions SET expires=0 WHERE user_id='outsider'")
        self.assertEqual(self.request("outsider")[0],401)

    def test_revocation_hides_existing_booking(self):
        with phase3.connect() as db:
            db.execute("UPDATE users SET approved=0 WHERE id='teacher'")
        self.assertEqual(self.request("student")[1]["bookings"],[])
        self.assertEqual(self.request("teacher")[1]["bookings"],[])

    def test_booking_survives_database_reconnect(self):
        with phase3.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM bookings WHERE id='booking'").fetchone()[0],1)

if __name__=="__main__":
    unittest.main()
