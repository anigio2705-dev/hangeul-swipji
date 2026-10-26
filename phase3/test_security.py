"""Adversarial local-only HTTP regression checks; never accesses Supabase."""
import http.client
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
import server

class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original_db = server.DB_PATH
        self.original_units = server.units
        server.DB_PATH = str(Path(self.temp.name) / 'security.sqlite3')
        server.units = lambda: [{'id':'SEC-UNIT','title':'Security unit','level':'A1','durationMinutes':30,'teacherGuide':['private guide']}]
        server.init_db()
        server.create_admin('admin@example.test','admin-password-123456')
        self.httpd = server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        self.httpd.failures = {}
        self.thread = threading.Thread(target=self.httpd.serve_forever,daemon=True)
        self.thread.start()
        self.admin = self.call('POST','/api/login',{'email':'admin@example.test','password':'admin-password-123456'})[2]
        self.teacher_data,self.teacher = self.register('teacher','teacher')
        self.learner_data,self.learner = self.register('learner','learner')
        self.other_data,self.other = self.register('other','learner')
        self.call('POST','/api/admin/verify',{'userId':self.teacher_data['id'],'approved':True,'reason':'Local test approval evidence only'},self.admin)
        start = time.time()+60
        _,r,_ = self.call('POST','/api/availability',{'start':start,'end':start+1800},self.teacher)
        self.slot = r['slotId']
        _,r,_ = self.call('POST','/api/bookings',{'teacherId':self.teacher_data['id'],'slotId':self.slot,'unitId':'SEC-UNIT'},self.learner)
        self.booking = r['bookingId']
    def tearDown(self):
        self.httpd.shutdown(); self.httpd.server_close(); self.thread.join()
        server.DB_PATH = self.original_db
        server.units = self.original_units
        self.temp.cleanup()
    def call(self,method,path,data=None,cookie=None,extra=None):
        h={'Content-Type':'application/json'}
        if cookie:h['Cookie']=cookie
        h.update(extra or {})
        c=http.client.HTTPConnection('127.0.0.1',self.httpd.server_port,timeout=5)
        c.request(method,path,body=json.dumps(data).encode() if data is not None else None,headers=h)
        r=c.getresponse(); raw=r.read(); ct=r.getheader('Content-Type',''); value=json.loads(raw) if 'application/json' in ct else raw
        cookie=r.getheader('Set-Cookie','').split(';')[0]
        status=r.status;c.close();return status,value,cookie
    def register(self,name,role):
        s,d,c=self.call('POST','/api/register',{'email':name+'@example.test','password':'long-password-123','nickname':name,'role':role,'adultConsent':True})
        self.assertEqual(s,200,d);return d['user'],c
    def test_admin_cannot_be_self_assigned_and_approval_is_protected(self):
        s,_,_=self.call('POST','/api/register',{'email':'evil@example.test','password':'long-password-123','nickname':'evil','role':'admin','adultConsent':True})
        self.assertEqual(s,400)
        s,_,_=self.call('POST','/api/admin/verify',{'userId':self.other_data['id'],'approved':True,'reason':'malicious approval request'},self.other)
        self.assertEqual(s,403)
        s,d,_=self.call('PUT','/api/profile',{'role':'admin','approved':True},self.other)
        self.assertEqual(s,200,d);self.assertEqual(d['user']['role'],'learner');self.assertFalse(d['user']['approved'])
    def test_idor_and_premature_completion_blocked(self):
        for action,payload in [('pay-test',{}),('join',{}),('complete',{}),('homework',{'text':'intrusion'}),('feedback',{'text':'intrusion','score':100}),('dispute',{'reason':'unauthorized dispute text'})]:
            s,_,_=self.call('POST',f'/api/bookings/{self.booking}/{action}',payload,self.other)
            self.assertEqual(s,403,action)
        s,_,_=self.call('POST',f'/api/bookings/{self.booking}/complete',{},self.learner)
        self.assertEqual(s,409)
        s,_,_=self.call('POST','/api/admin/settle',{'bookingId':self.booking},self.admin)
        self.assertEqual(s,409)
    def test_csrf_host_and_static_leakage(self):
        s,_,_=self.call('PUT','/api/profile',{'nickname':'CSRF'},self.learner,{'Origin':'https://evil.test'})
        self.assertEqual(s,403)
        s,_,_=self.call('GET','/api/me',cookie=self.learner,extra={'Host':'evil.test'})
        self.assertEqual(s,403)
        for path in ['/server.py','/schema.sql','/content.json','/../speaking-config.js','/%2e%2e/server.py','/.env']:
            s,_,_=self.call('GET',path)
            self.assertEqual(s,404,path)
    def test_adult_guard_and_password_policy(self):
        for changes in [{'adultConsent':False},{'adultConsent':'true'},{'password':'short'},{'role':'moderator'}]:
            d={'email':'guard@example.test','password':'long-password-123','nickname':'guard','role':'learner','adultConsent':True};d.update(changes)
            s,_,_=self.call('POST','/api/register',d)
            self.assertEqual(s,400,changes)
    def test_duplicate_charge_and_refund_reversal_are_idempotent(self):
        endpoint=f'/api/bookings/{self.booking}'
        for _ in range(2):
            s,_,_=self.call('POST',endpoint+'/pay-test',{},self.learner);self.assertEqual(s,200)
        _,d,_=self.call('POST',endpoint+'/dispute',{'category':'refund','reason':'A local test refund request with evidence'},self.learner)
        did=d['disputeId']
        s,_,_=self.call('POST','/api/admin/disputes/'+did,{'decision':'refund','reason':'Evidence confirmed local test refund'},self.admin);self.assertEqual(s,200)
        s,_,_=self.call('POST','/api/admin/disputes/'+did,{'decision':'refund','reason':'Repeated decision must not double-refund'},self.admin);self.assertEqual(s,409)
        with server.connect() as db:
            rows=db.execute('SELECT kind,amount FROM ledger WHERE booking_id=?',(self.booking,)).fetchall()
            self.assertEqual(len(rows),2)
            self.assertEqual(sum(x['amount'] for x in rows),0)
            with self.assertRaises(Exception):db.execute('UPDATE ledger SET amount=0')
            with self.assertRaises(Exception):db.execute('DELETE FROM audit')
    def test_booking_conflict_and_password_not_exposed(self):
        s,_,_=self.call('POST','/api/bookings',{'teacherId':self.teacher_data['id'],'slotId':self.slot,'unitId':'SEC-UNIT'},self.other)
        self.assertEqual(s,409)
        _,d,_=self.call('GET','/api/teachers',cookie=self.other)
        for teacher in d['teachers']:
            self.assertNotIn('password',teacher);self.assertNotIn('email',teacher)
        _,d,_=self.call('GET','/api/bookings',cookie=self.other)
        self.assertEqual(d['bookings'],[])
        _,d,_=self.call('GET','/api/units/SEC-UNIT',cookie=self.learner)
        self.assertNotIn('teacherGuide',d['unit'])

if __name__=='__main__':unittest.main()
