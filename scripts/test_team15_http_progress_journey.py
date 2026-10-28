"""Actual loopback HTTP and persistent SQLite E2E for Team11 account/progress boundary.
Nonproduction only. Fails hard on HTTP, isolation, replay or persistence errors.
"""
import http.client
import importlib
import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"team11"/"phase3"))
server=importlib.import_module("server")

class RealHttpProgressJourney(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.original=server.DB_PATH
        server.DB_PATH=os.path.join(self.temp.name,"journey.sqlite3")
        server.init_db()
        self.http=ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
        self.http.failures={}
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True)
        self.thread.start()
        self.cookies={}

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=5)
        server.DB_PATH=self.original
        self.temp.cleanup()

    def request(self,method,path,account=None,payload=None,expected=200):
        conn=http.client.HTTPConnection("127.0.0.1",self.http.server_port,timeout=8)
        headers={"Host":f"127.0.0.1:{self.http.server_port}"}
        if account in self.cookies: headers["Cookie"]=self.cookies[account]
        if payload is not None: headers["Content-Type"]="application/json"
        try:
            conn.request(method,path,body=json.dumps(payload).encode() if payload is not None else None,headers=headers)
            response=conn.getresponse()
            raw=response.read()
            result=json.loads(raw)
            cookie=response.getheader("Set-Cookie")
            if cookie and account: self.cookies[account]=cookie.split(";",1)[0]
            self.assertEqual(response.status,expected,(method,path,result))
            return result
        finally: conn.close()

    def test_register_login_progress_isolation_restart(self):
        password="NonProduction!2026Password"
        for name in ("student-a","student-b"):
            data={"email":name+"@example.test","password":password,"nickname":name,
                  "role":"learner","adultConsent":True}
            self.request("POST","/api/register",name,data)
        self.request("POST","/api/free-progress","student-a",{"stage":1,"lesson":1})
        self.request("POST","/api/free-progress","student-a",{"stage":1,"lesson":1})
        self.request("POST","/api/free-progress/import","student-a",
                     {"completed":[{"stage":2,"lesson":4},{"stage":1,"lesson":1}]})
        a=self.request("GET","/api/free-progress","student-a")
        b=self.request("GET","/api/free-progress","student-b")
        self.assertEqual({(x["stage"],x["lesson"]) for x in a["completed"]},{(1,1),(2,4)})
        self.assertEqual(b["completed"],[])
        self.cookies.pop("student-a")
        self.request("POST","/api/login","student-a",
                     {"email":"student-a@example.test","password":password})
        self.assertEqual(self.request("GET","/api/free-progress","student-a")["count"],2)
        self.assertEqual(self.request("GET","/api/teachers","student-a")["total"],0)
        with sqlite3.connect(server.DB_PATH) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM free_lesson_progress").fetchone()[0],2)
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=5)
        self.http=ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
        self.http.failures={}
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True)
        self.thread.start()
        self.assertEqual(self.request("GET","/api/free-progress","student-a")["count"],2)
        self.assertEqual(self.request("GET","/api/free-progress","student-b")["count"],0)

if __name__=="__main__":unittest.main(verbosity=2)
