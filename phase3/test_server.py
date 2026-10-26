"""Deterministic local TEST transactions; time travel is test-only, never an API."""
import concurrent.futures
import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
import server

class Client:
    def __init__(self,port): self.port,self.cookie=port,''
    def call(self,path,data=None,method=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=10)
        headers={'Content-Type':'application/json','Cookie':self.cookie,'Origin':f'http://127.0.0.1:{self.port}'}
        conn.request(method or ('GET' if data is None else 'POST'),path,None if data is None else json.dumps(data),headers)
        response=conn.getresponse(); body=json.loads(response.read())
        if response.getheader('Set-Cookie'): self.cookie=response.getheader('Set-Cookie').split(';')[0]
        conn.close(); return response.status,body

class PlatformTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); server.DB_PATH=str(Path(self.temp.name)/'test.sqlite3'); server.init_db()
        self.unit={'id':'test-unit','title':'Test original unit','durationMinutes':30,'teacherGuide':['teacher only']}
        self.units_patch=patch.object(server,'units',lambda:[self.unit]);self.units_patch.start()
        self.clock=2000000000.0
        self.time_patch=patch.object(server.time,'time',lambda:self.clock);self.time_patch.start()
        self.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);self.http.failures={}
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.admin=Client(self.http.server_port);server.create_admin('admin@example.com','Admin Password 12345');self.assertEqual(200,self.admin.call('/api/login',{'email':'admin@example.com','password':'Admin Password 12345'})[0])
        self.learner,self.l=self.register('learner')
        self.teacher,self.t=self.register('teacher')
        self.outsider,self.o=self.register('learner','outsider')
        self.assertEqual(200,self.admin.call('/api/admin/verify',{'userId':self.t['id'],'approved':True,'reason':'Local test document and adult review only'})[0])
        status,result=self.teacher.call('/api/availability',{'start':self.clock+600,'end':self.clock+4200});self.assertEqual(200,status);self.slot=result['slotId']
    def tearDown(self):
        self.http.shutdown(); self.http.server_close();self.thread.join();self.units_patch.stop();self.time_patch.stop();self.temp.cleanup()
    def register(self,role,suffix=None,referral=None):
        client=Client(self.http.server_port);d={'email':(suffix or role)+'@example.com','password':'Password12345!','nickname':suffix or role,'role':role,'adultConsent':True}
        if referral:d['referralCode']=referral
        status,result=client.call('/api/register',d);self.assertEqual(200,status,result);return client,result['user']
    def book(self,client=None,slot=None,referral=None):
        body={'teacherId':self.t['id'],'slotId':slot or self.slot,'unitId':'test-unit'}
        if referral:body['referralCode']=referral
        return (client or self.learner).call('/api/bookings',body)
    def booking(self):
        status,result=self.book();self.assertEqual(200,status,result);return result['bookingId']
    def action(self,client,bid,action,body=None):return client.call('/api/bookings/'+bid+'/'+action,body or {})
    def finish(self,bid):
        self.assertEqual(200,self.action(self.learner,bid,'pay-test')[0]);self.clock+=600
        for client in (self.learner,self.teacher):self.assertEqual(200,self.action(client,bid,'join')[0])
        for _ in range(30):
            self.clock+=60
            for client in (self.learner,self.teacher):self.assertEqual(200,self.action(client,bid,'attendance')[0])
        self.assertEqual(200,self.admin.call('/api/admin/evidence',{'bookingId':bid,'reason':'Test-only deterministic attendance evidence review'})[0])
        for client in (self.learner,self.teacher):self.assertEqual(200,self.action(client,bid,'complete')[0])
    def test_signup_admin_escalation_and_underage_denied(self):
        for role,consent in [('admin',True),('learner',False)]:
            c=Client(self.http.server_port);status,_=c.call('/api/register',{'email':'invalid@example.com','password':'Password12345!','nickname':'Invalid','role':role,'adultConsent':consent});self.assertEqual(400,status)
    def test_approval_and_search_filters(self):
        status,result=self.learner.call('/api/teachers?role=teacher&maxPrice=20000');self.assertEqual(200,status);self.assertEqual([self.t['id']],[x['id'] for x in result['teachers']]);self.assertNotIn('referral_code',result['teachers'][0])
        self.teacher.call('/api/profile',{'price':21000},'PUT')
        self.assertEqual([],self.learner.call('/api/teachers')[1]['teachers'])
        self.assertEqual(403,self.teacher.call('/api/admin/verify',{'userId':self.t['id'],'approved':True,'reason':'Untrusted self approval attempt'})[0])
    def test_duplicate_booking_concurrent(self):
        with concurrent.futures.ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:self.book(),range(2)))
        self.assertEqual([200,409],sorted(x[0] for x in results))
    def test_overlapping_teacher_and_learner_slots(self):
        self.assertEqual(409,self.teacher.call('/api/availability',{'start':self.clock+700,'end':self.clock+4400})[0])
        bid=self.booking();other_teacher,other=self.register('partner');self.admin.call('/api/admin/verify',{'userId':other['id'],'approved':True,'reason':'Local test approval evidence only'})
        _,s=other_teacher.call('/api/availability',{'start':self.clock+700,'end':self.clock+4400})
        self.assertEqual(409,self.learner.call('/api/bookings',{'teacherId':other['id'],'slotId':s['slotId'],'unitId':'test-unit'})[0])
    def test_pay_is_idempotent_and_no_real_money(self):
        bid=self.booking()
        for _ in range(2):
            status,result=self.action(self.learner,bid,'pay-test');self.assertEqual(200,status);self.assertFalse(result['chargedRealMoney'])
        with server.connect() as db:self.assertEqual(1,db.execute("SELECT count(*) FROM ledger WHERE kind='test_charge'").fetchone()[0])
        self.assertEqual(403,self.action(self.teacher,bid,'pay-test')[0])
    def test_idor_and_unauthorized_state_changes(self):
        bid=self.booking()
        for action in ['pay-test','join','complete','cancel','homework','feedback','dispute']:
            self.assertEqual(403,self.action(self.outsider,bid,action,{'reason':'malicious outsider write','text':'attack','score':100})[0])
        self.assertEqual(403,self.outsider.call('/api/bookings/'+bid+'/unit')[0]);self.assertEqual(403,self.outsider.call('/api/admin')[0])
    def test_unit_and_rates_immutable(self):
        bid=self.booking();self.unit['durationMinutes']=1;self.unit['title']='Changed source'
        teacher=self.teacher.call('/api/bookings/'+bid+'/unit')[1];learner=self.learner.call('/api/bookings/'+bid+'/unit')[1]
        self.assertEqual('Test original unit',teacher['unit']['title']);self.assertEqual(30,teacher['unit']['durationMinutes']);self.assertEqual(teacher['sha256'],learner['sha256']);self.assertNotIn('teacherGuide',learner['unit'])
        with server.connect() as db:
            for query in ['UPDATE rate_snapshots SET commission_bps=9000','DELETE FROM rate_snapshots','UPDATE unit_snapshots SET content=\'{}\'']:
                with self.assertRaises(sqlite3.IntegrityError):db.execute(query)
    def test_completion_insufficient_and_admin_evidence_gate(self):
        bid=self.booking();self.action(self.learner,bid,'pay-test');self.assertEqual(409,self.action(self.learner,bid,'join')[0]);self.clock+=600;self.action(self.learner,bid,'join');self.assertEqual(409,self.action(self.learner,bid,'complete')[0]);self.assertEqual(409,self.admin.call('/api/admin/settle',{'bookingId':bid})[0])
    def test_heartbeat_no_credit_outside_slot_or_large_gap(self):
        bid=self.booking();self.action(self.learner,bid,'pay-test');self.clock+=300;self.action(self.learner,bid,'join');self.clock+=60;self.action(self.learner,bid,'attendance')
        with server.connect() as db:self.assertEqual(0,db.execute('SELECT seconds FROM attendance').fetchone()[0])
        self.clock+=600;self.action(self.learner,bid,'attendance')
        with server.connect() as db:self.assertEqual(0,db.execute('SELECT seconds FROM attendance').fetchone()[0])
        self.clock+=60;self.action(self.learner,bid,'attendance')
        with server.connect() as db:self.assertEqual(60,db.execute('SELECT seconds FROM attendance').fetchone()[0])
    def test_full_30min_complete_settle_refund_and_review_exclusion(self):
        bid=self.booking();self.finish(bid)
        self.assertEqual(200,self.action(self.learner,bid,'review',{'rating':5,'text':'A test review'})[0])
        self.assertEqual(200,self.action(self.learner,bid,'homework',{'text':'Original homework'})[0]);self.assertEqual(200,self.action(self.teacher,bid,'feedback',{'text':'Good progress','score':80})[0])
        first=self.admin.call('/api/admin/settle',{'bookingId':bid});self.assertEqual(200,first[0]);self.assertFalse(first[1]['realPayout']);self.assertEqual(200,self.admin.call('/api/admin/settle',{'bookingId':bid})[0])
        _,case=self.action(self.learner,bid,'dispute',{'category':'connection','reason':'Test connection failure evidence'})
        self.assertEqual(409,self.admin.call('/api/admin/settle',{'bookingId':bid})[0])
        self.assertEqual(200,self.admin.call('/api/admin/disputes/'+case['disputeId'],{'decision':'refund','reason':'Test-only refund approved after evidence'})[0])
        with server.connect() as db:
            for group in db.execute("SELECT replace(kind,'_reversal','') AS k,sum(amount) AS total FROM ledger GROUP BY k"):self.assertEqual(0,group['total'])
            with self.assertRaises(sqlite3.IntegrityError):db.execute('DELETE FROM audit')
        self.assertEqual(0,self.learner.call('/api/teachers')[1]['teachers'][0]['reviewCount'])
        self.assertEqual(200,self.action(self.teacher,bid,'appeal',{'disputeId':case['disputeId'],'reason':'Teacher appeal with retained evidence'})[0])
    def test_direct_referral_only_and_no_signup_reward(self):
        with server.connect() as db:self.assertEqual(0,db.execute('SELECT count(*) FROM ledger').fetchone()[0])
        status,result=self.book(referral=self.l['referral_code']);self.assertEqual(400,status)
        status,result=self.book(referral=self.o['referral_code']);self.assertEqual(200,status);bid=result['bookingId'];self.finish(bid)
        self.admin.call('/api/admin/settle',{'bookingId':bid})
        with server.connect() as db:
            reward=db.execute("SELECT * FROM ledger WHERE kind='test_referral_accrual'").fetchone();self.assertEqual(600,reward['amount']);self.assertEqual(self.o['id'],reward['beneficiary'])
    def test_reschedule_requires_actual_both_participant_consents(self):
        bid=self.booking();self.action(self.learner,bid,'pay-test');_,replacement=self.teacher.call('/api/availability',{'start':self.clock+5000,'end':self.clock+8600})
        _,case=self.action(self.learner,bid,'dispute',{'category':'connection','reason':'Test need a mutually agreed replacement'})
        body={'decision':'reschedule','slotId':replacement['slotId'],'learnerConsent':True,'teacherConsent':True,'reason':'Mutual test replacement evidence'}
        endpoint='/api/admin/disputes/'+case['disputeId'];self.assertEqual(400,self.admin.call(endpoint,body)[0])
        self.action(self.learner,bid,'reschedule-consent',{'slotId':replacement['slotId']});self.assertEqual(400,self.admin.call(endpoint,body)[0])
        self.action(self.teacher,bid,'reschedule-consent',{'slotId':replacement['slotId']});self.assertEqual(200,self.admin.call(endpoint,body)[0])
        with server.connect() as db:self.assertEqual(replacement['slotId'],db.execute('SELECT slot_id FROM bookings WHERE id=?',(bid,)).fetchone()[0])
    def test_scenarios_integer_conservation(self):
        status,result=self.learner.call('/api/scenarios?price=21999&taxBps=500');self.assertEqual(200,status);self.assertEqual(9,len(result['scenarios']))
        for x in result['scenarios']:self.assertEqual(x['gross'],sum(x[k] for k in ['teacher','referral','processor','refund','tax','platform']))
        self.assertEqual(400,self.learner.call('/api/scenarios?taxBps=-1')[0])
    def test_logout_revokes_session(self):
        old=self.learner.cookie;self.learner.call('/api/logout',{});self.learner.cookie=old;self.assertEqual(401,self.learner.call('/api/me')[0])

if __name__=='__main__':unittest.main(verbosity=2)
