"""Real authentication/SQLite HTTP journey for free study, quiz, resume, logout, restart.

Runs against the production-shaped Team11 Handler without monkeypatching routes.
All accounts and funds are nonproduction.
"""
import http.client
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
import server

class AuthenticatedFreeCourseJourney(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old_db=server.DB_PATH
        server.DB_PATH=os.path.join(self.tmp.name,'progress.sqlite3')
        server.init_db()
        self.start_http()

    def start_http(self):
        self.http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        self.http.failures={}
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True)
        self.thread.start()

    def stop_http(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=5)

    def tearDown(self):
        self.stop_http()
        server.DB_PATH=self.old_db
        self.tmp.cleanup()

    def call(self,path,method='GET',payload=None,cookie=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.http.server_port,timeout=10)
        headers={}
        if cookie: headers['Cookie']=cookie
        if payload is not None: headers['Content-Type']='application/json'
        try:
            conn.request(method,path,json.dumps(payload) if payload is not None else None,headers)
            resp=conn.getresponse()
            return resp.status,json.loads(resp.read()),resp.getheader('Set-Cookie')
        finally:
            conn.close()

    def account(self,email):
        status,data,cookie=self.call('/api/register','POST',{'email':email,
            'password':'Disposable-Password-12345!','nickname':'Study Student',
            'role':'learner','adultConsent':True})
        self.assertEqual(status,200,data)
        return data['user']['id'],cookie.split(';',1)[0]

    def test_account_quiz_logout_relogin_restart_and_security(self):
        first,a=self.account('study-a@example.test')
        second,b=self.account('study-b@example.test')
        self.assertNotEqual(first,second)
        self.assertEqual(self.call('/api/free-progress',cookie=None)[0],401)
        self.assertEqual(self.call('/api/free-progress/quiz',cookie=None)[0],401)
        self.assertEqual(self.call('/api/free-progress/position',cookie=None)[0],401)
        self.assertEqual(self.call('/api/free-progress','POST',{'stage':1,'lesson':1},a)[0],200)
        self.assertEqual(self.call('/api/free-progress/import','POST',{'completed':[{'stage':1,'lesson':1},{'stage':2,'lesson':4}]},a)[0],200)
        result={'stage':1,'lesson':1,'score':8,'maxScore':10,'requestId':'attempt-a-1'}
        self.assertEqual(self.call('/api/free-progress/quiz','POST',result,a)[1]['duplicate'],False)
        self.assertEqual(self.call('/api/free-progress/quiz','POST',result,a)[1]['duplicate'],True)
        self.assertEqual(self.call('/api/free-progress/quiz','POST',dict(result,score=9),a)[0],409)
        self.assertEqual(self.call('/api/free-progress/position','POST',{'stage':2,'lesson':5},a)[0],200)
        self.assertEqual(self.call('/api/free-progress',cookie=b)[1]['count'],0)
        self.assertEqual(self.call('/api/free-progress/quiz',cookie=b)[1]['count'],0)
        self.assertIsNone(self.call('/api/free-progress/position',cookie=b)[1]['position'])
        for wrong in ({'stage':8,'lesson':1,'score':5,'maxScore':10,'requestId':'bad1'},
                      {'stage':1,'lesson':51,'score':5,'maxScore':10,'requestId':'bad2'},
                      {'stage':1,'lesson':1,'score':11,'maxScore':10,'requestId':'bad3'},
                      {'stage':1,'lesson':1,'score':True,'maxScore':10,'requestId':'bad4'},
                      {'stage':1,'lesson':1,'score':3,'maxScore':10,'requestId':''}):
            self.assertEqual(self.call('/api/free-progress/quiz','POST',wrong,a)[0],400)
        self.assertEqual(self.call('/api/free-progress/position','POST',{'stage':1,'lesson':False},a)[0],400)
        status,_,clear=self.call('/api/logout','POST',{},a)
        self.assertEqual(status,200)
        self.assertIn('Max-Age=0',clear)
        self.assertEqual(self.call('/api/free-progress',cookie=a)[0],401)
        self.assertEqual(self.call('/api/free-progress/quiz',cookie=a)[0],401)
        status,_,cookie=self.call('/api/login','POST',{
            'email':'study-a@example.test','password':'Disposable-Password-12345!'})
        self.assertEqual(status,200)
        new_cookie=cookie.split(';',1)[0]
        self.assertNotEqual(a,new_cookie)
        self.assertEqual(self.call('/api/free-progress',cookie=new_cookie)[1]['count'],2)
        self.assertEqual(self.call('/api/free-progress/quiz',cookie=new_cookie)[1]['results'][0]['score'],8)
        self.assertEqual(self.call('/api/free-progress/position',cookie=new_cookie)[1]['position']['lesson'],5)
        with server.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM free_quiz_results WHERE user_id=?',(first,)).fetchone()[0],1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM free_lesson_progress WHERE user_id=?',(first,)).fetchone()[0],2)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM free_resume_positions WHERE user_id=?',(second,)).fetchone()[0],0)
        self.stop_http()
        self.start_http()
        self.assertEqual(self.call('/api/free-progress',cookie=new_cookie)[1]['count'],2)
        self.assertEqual(self.call('/api/free-progress/quiz',cookie=new_cookie)[1]['count'],1)
        self.assertEqual(self.call('/api/free-progress/position',cookie=new_cookie)[1]['position']['stage'],2)

    def test_duplicate_account_request_ids_are_scoped_per_member(self):
        _,a=self.account('quiz-a@example.test')
        _,b=self.account('quiz-b@example.test')
        quiz={'stage':7,'lesson':50,'score':10,'maxScore':10,'requestId':'shared-id'}
        self.assertEqual(self.call('/api/free-progress/quiz','POST',quiz,a)[0],200)
        self.assertEqual(self.call('/api/free-progress/quiz','POST',quiz,b)[0],200)
        self.assertEqual(self.call('/api/free-progress/quiz',cookie=a)[1]['count'],1)
        self.assertEqual(self.call('/api/free-progress/quiz',cookie=b)[1]['count'],1)

if __name__=='__main__':
    unittest.main()
