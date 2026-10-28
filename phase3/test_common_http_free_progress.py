"""Real HTTP integration of authenticated free progress and persistent SQLite."""
import hashlib
import http.client
import json
import os
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
import server

class FreeProgressHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.original=server.DB_PATH
        server.DB_PATH=os.path.join(cls.tmp.name,"progress.sqlite3")
        server.init_db()
        with server.connect() as db:
            for uid,role in (("learner-a","learner"),("learner-b","learner"),("provider","teacher")):
                db.execute("INSERT INTO users(id,email,password,nickname,role,approved,referral_code,created_at) VALUES(?,?,?,?,?,?,?,?)",
                           (uid,uid+"@example.test","dummy",uid,role,1 if role=="teacher" else 0,"ref-"+uid,time.time()))
                db.execute("INSERT INTO sessions(token,user_id,expires) VALUES(?,?,?)",
                           (hashlib.sha256(("session-token-"+uid).encode()).hexdigest(),uid,time.time()+3600))
        cls.http=ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
        cls.http.failures={}
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join(timeout=5)
        server.DB_PATH=cls.original
        cls.tmp.cleanup()

    def request(self,uid,method="GET",data=None):
        conn=http.client.HTTPConnection("127.0.0.1",self.http.server_port,timeout=5)
        headers={"Content-Type":"application/json"}
        if uid: headers["Cookie"]="hs3=session-token-"+uid
        try:
            conn.request(method,"/api/free-progress",body=json.dumps(data or {}) if method=="POST" else None,headers=headers)
            resp=conn.getresponse()
            return resp.status,json.loads(resp.read())
        finally:
            conn.close()

    def test_authenticated_progress_persists_across_connections(self):
        self.assertEqual(self.request("learner-a","POST",{"stage":1,"lesson":3})[0],200)
        with server.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM free_lesson_progress WHERE user_id='learner-a' AND stage=1 AND lesson=3").fetchone()[0],1)
        status,result=self.request("learner-a")
        self.assertEqual(status,200)
        self.assertIn(3,[x["lesson"] for x in result["completed"] if x["stage"]==1])

    def test_duplicate_completion_idempotent(self):
        for _ in range(2):
            self.assertEqual(self.request("learner-a","POST",{"stage":7,"lesson":50})[0],200)
        with server.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM free_lesson_progress WHERE user_id='learner-a' AND stage=7 AND lesson=50").fetchone()[0],1)

    def test_other_account_progress_isolated(self):
        self.assertEqual(self.request("learner-b")[1]["completed"],[])

    def test_invalid_or_unauthenticated_rejected(self):
        self.assertEqual(self.request(None)[0],401)
        self.assertEqual(self.request("provider")[0],403)
        for payload in ({"stage":0,"lesson":1},{"stage":1,"lesson":51},{"stage":True,"lesson":1}):
            self.assertEqual(self.request("learner-a","POST",payload)[0],400)

if __name__=="__main__":
    unittest.main()
