"""15-minute scope: real loopback HTTP + SQLite signup/login/progress/relogin/restore.
Uses Team11 actual server and Team12's expected authenticated API contract.
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

class MinimalProgressHTTP(unittest.TestCase):
 def test_signup_login_progress_relogin_restore(self):
  with tempfile.TemporaryDirectory() as directory:
   old=server.DB_PATH
   server.DB_PATH=Path(directory)/"progress.sqlite3"
   httpd=None
   try:
    server.init_db()
    httpd=ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
    httpd.failures={}
    thread=threading.Thread(target=httpd.serve_forever,daemon=True)
    thread.start()
    cookie=None
    def call(method,path,body=None):
     nonlocal cookie
     connection=http.client.HTTPConnection("127.0.0.1",httpd.server_port,timeout=10)
     headers={"Content-Type":"application/json"}
     if cookie:headers["Cookie"]=cookie
     try:
      connection.request(method,path,json.dumps(body) if body is not None else None,headers)
      response=connection.getresponse()
      data=json.loads(response.read())
      print(json.dumps({"method":method,"path":path,"status":response.status,"count":data.get("count"),"error":data.get("error")},ensure_ascii=False),flush=True)
      if response.getheader("Set-Cookie"):cookie=response.getheader("Set-Cookie").split(";",1)[0]
      self.assertEqual(response.status,200,data)
      return data
     finally:connection.close()
    account={"email":"minimal-student@example.test","password":"TestPassword!2026","nickname":"Student Test","role":"learner","adultConsent":True}
    user=call("POST","/api/register",account)["user"]["id"]
    cookie=None
    self.assertEqual(call("POST","/api/login",{"email":account["email"],"password":account["password"]})["user"]["id"],user)
    call("POST","/api/free-progress",{"stage":1,"lesson":1})
    self.assertEqual(call("GET","/api/free-progress")["count"],1)
    cookie=None
    self.assertEqual(call("POST","/api/login",{"email":account["email"],"password":account["password"]})["user"]["id"],user)
    saved=call("GET","/api/free-progress")["completed"]
    self.assertEqual([(r["stage"],r["lesson"]) for r in saved],[(1,1)])
    with sqlite3.connect(server.DB_PATH) as db:
     self.assertEqual(db.execute("SELECT count(*) FROM free_lesson_progress WHERE user_id=?",(user,)).fetchone()[0],1)
   finally:
    if httpd:
     httpd.shutdown();httpd.server_close();thread.join(timeout=5)
    server.DB_PATH=old

if __name__=="__main__":unittest.main(verbosity=2)
