"""Minimal cross-feature HTTP/SQLite integration: real register/login, learning, teacher discovery, booking."""
import http.client
import json
import os
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
import server

class CommonHttpJourney(unittest.TestCase):
    def test_register_learning_booking_one_database(self):
        with tempfile.TemporaryDirectory() as directory:
            original=server.DB_PATH
            server.DB_PATH=os.path.join(directory,"journey.sqlite3")
            http=None
            try:
                server.init_db()
                http=ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
                http.failures={}
                thread=threading.Thread(target=http.serve_forever,daemon=True)
                thread.start()
                def request(method,path,data=None,cookie=None):
                    conn=http.client.HTTPConnection("127.0.0.1",http.server_port,timeout=10)
                    headers={"Content-Type":"application/json"}
                    if cookie: headers["Cookie"]=cookie
                    try:
                        conn.request(method,path,json.dumps(data) if data is not None else None,headers)
                        response=conn.getresponse()
                        body=json.loads(response.read())
                        return response.status,body,response.getheader("Set-Cookie")
                    finally:conn.close()
                def register(role,email):
                    status,body,cookie=request("POST","/api/register",{
                        "email":email,"password":"test-password-123456",
                        "nickname":"Integration Tester","role":role,"adultConsent":True})
                    self.assertEqual(status,200,body)
                    self.assertTrue(cookie)
                    return body["user"]["id"],cookie.split(";",1)[0]
                student,sc=register("learner","journey-student@example.test")
                teacher,tc=register("teacher","journey-teacher@example.test")
                other,oc=register("learner","journey-other@example.test")
                status,body,_=request("POST","/api/free-progress",{"stage":1,"lesson":1},sc)
                self.assertEqual(status,200,body)
                self.assertEqual(request("GET","/api/free-progress",cookie=oc)[1]["completed"],[])
                status,body,login_cookie=request("POST","/api/login",{
                    "email":"journey-student@example.test","password":"test-password-123456"})
                self.assertEqual(status,200,body)
                sc=login_cookie.split(";",1)[0]
                self.assertEqual(request("GET","/api/free-progress",cookie=sc)[1]["count"],1)
                with server.connect() as db:
                    db.execute("UPDATE users SET approved=1 WHERE id=?",(teacher,))
                    db.execute("INSERT INTO slots(id,teacher_id,start,end) VALUES(?,?,?,?)",
                               ("journey-slot",teacher,time.time()+7200,time.time()+10800))
                status,body,_=request("GET","/api/teachers",cookie=sc)
                self.assertEqual(status,200,body)
                self.assertIn(teacher,json.dumps(body,ensure_ascii=False))
                status,body,_=request("GET","/api/units",cookie=sc)
                self.assertEqual(status,200,body)
                self.assertTrue(body.get("units"))
                unit=body["units"][0]["id"]
                status,body,_=request("POST","/api/bookings",{
                    "teacherId":teacher,"slotId":"journey-slot","unitId":unit},sc)
                self.assertEqual(status,200,body)
                with server.connect() as db:
                    self.assertEqual(db.execute("SELECT count(*) FROM bookings WHERE learner_id=? AND teacher_id=?",(student,teacher)).fetchone()[0],1)
                    self.assertEqual(db.execute("SELECT count(*) FROM free_lesson_progress WHERE user_id=?",(student,)).fetchone()[0],1)
                status,body,_=request("GET","/api/bookings",cookie=oc)
                self.assertEqual(status,200,body)
                self.assertEqual(body["bookings"],[])
            finally:
                if http is not None:
                    http.shutdown()
                    http.server_close()
                    thread.join(timeout=5)
                server.DB_PATH=original

if __name__=="__main__":unittest.main()
