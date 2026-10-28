"""Nonproduction real HTTP + SQLite integration. Deliberately does NOT forge attendance.
Reports a real booking and the actual rejection of premature completion.
"""
import http.client,json,os,sys,tempfile,threading,time,unittest,sqlite3
from pathlib import Path
from http.server import ThreadingHTTPServer
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'team11'/'phase3'))
import server

class RealJourney(unittest.TestCase):
 def test_real_http_account_progress_booking_and_completion_gate(self):
  with tempfile.TemporaryDirectory() as tmp:
   original=server.DB_PATH;server.DB_PATH=Path(tmp)/'real.sqlite3'
   httpd=None
   try:
    server.init_db()
    httpd=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);httpd.failures={}
    thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
    cookies={}
    def call(actor,method,path,payload=None,expected=200):
     conn=http.client.HTTPConnection('127.0.0.1',httpd.server_port,timeout=12)
     headers={'Content-Type':'application/json'}
     if actor in cookies:headers['Cookie']=cookies[actor]
     try:
      conn.request(method,path,json.dumps(payload) if payload is not None else None,headers)
      response=conn.getresponse();result=json.loads(response.read())
      if response.getheader('Set-Cookie'):cookies[actor]=response.getheader('Set-Cookie').split(';',1)[0]
      print(json.dumps({'actor':actor,'method':method,'path':path,'status':response.status,'error':result.get('error')},ensure_ascii=False),flush=True)
      self.assertEqual(response.status,expected,result)
      return result
     finally:conn.close()
    pw='NonProduction!2026Password'
    def register(actor,role):
     return call(actor,'POST','/api/register',{'email':actor+'@example.test','password':pw,'nickname':'Integration '+actor,'role':role,'adultConsent':True})['user']['id']
    learner=register('student','learner');teacher=register('teacher','teacher');register('outsider','learner')
    cookies.pop('student')
    self.assertEqual(call('student','POST','/api/login',{'email':'student@example.test','password':pw})['user']['id'],learner)
    call('student','POST','/api/free-progress',{'stage':1,'lesson':1})
    self.assertEqual(call('outsider','GET','/api/free-progress')['count'],0)
    cookies.pop('student')
    call('student','POST','/api/login',{'email':'student@example.test','password':pw})
    self.assertEqual(call('student','GET','/api/free-progress')['count'],1)
    with server.connect() as db:
     db.execute('UPDATE users SET approved=1 WHERE id=?',(teacher,))
     db.execute('INSERT INTO slots(id,teacher_id,start,end) VALUES(?,?,?,?)',('test-slot',teacher,time.time()+3600,time.time()+7200))
    teachers=call('student','GET','/api/teachers')['teachers']
    self.assertTrue(any(x['id']==teacher for x in teachers))
    units=call('student','GET','/api/units')['units']
    self.assertTrue(units)
    booking=call('student','POST','/api/bookings',{'teacherId':teacher,'slotId':'test-slot','unitId':units[0]['id']})['bookingId']
    self.assertEqual(call('outsider','GET','/api/bookings')['bookings'],[])
    with server.connect() as db:
     row=db.execute('SELECT learner_id,teacher_id,status,price FROM bookings WHERE id=?',(booking,)).fetchone()
     self.assertEqual((row['learner_id'],row['teacher_id']), (learner,teacher))
     self.assertGreater(row['price'],0)
    # No invented attendance or test settlement: server MUST reject premature completion.
    call('student','POST','/api/bookings/'+booking+'/complete',{},expected=409)
    print('BOUNDARY: real HTTP booking succeeded; Team13 instant match and verified completion not exercised',flush=True)
   finally:
    if httpd:
     httpd.shutdown();httpd.server_close();thread.join(timeout=5)
    server.DB_PATH=original
if __name__=='__main__':unittest.main(verbosity=2)
