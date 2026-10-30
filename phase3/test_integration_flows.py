"""HTTP-level provider/auth contracts. These never use external accounts."""
import hashlib
import hmac
import http.client
import json
import os
import unittest
from unittest.mock import patch
import test_server as fixtures
import server

class IntegrationFlowTests(unittest.TestCase):
    setUp=fixtures.PlatformTests.setUp
    tearDown=fixtures.PlatformTests.tearDown
    register=fixtures.PlatformTests.register
    book=fixtures.PlatformTests.book
    booking=fixtures.PlatformTests.booking
    action=fixtures.PlatformTests.action
    def checkout(self,bid):
        self.obj={'id':'cs_test_http_contract','object':'checkout.session','url':'https://checkout.stripe.com/c/pay/test','livemode':False,'mode':'payment','currency':'krw','amount_total':20000,'client_reference_id':bid,'metadata':{'booking_id':bid,'hs_mode':'phase3-test-only'},'status':'complete','payment_status':'paid'}
        with patch.dict(os.environ,{'HS_STRIPE_TEST_SECRET_KEY':'sk_test_offline_contract_123456'}),patch.object(server.payments,'_transport',lambda *a,**k:json.dumps(self.obj).encode()):
            s,d=self.action(self.learner,bid,'checkout-test');self.assertEqual(200,s,d)
        return self.obj
    def webhook(self,event_id='evt_http_1',changes=None,signature_bad=False):
        obj=dict(self.obj,**(changes or {}));raw=json.dumps({'id':event_id,'livemode':False,'type':'checkout.session.completed','data':{'object':obj}}).encode();secret='whsec_http_contract_only_1234';stamp=str(int(self.clock));sig=hmac.new(secret.encode(),stamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()
        if signature_bad:sig='0'*64
        c=http.client.HTTPConnection('127.0.0.1',self.http.server_port)
        with patch.dict(os.environ,{'HS_STRIPE_TEST_WEBHOOK_SECRET':secret}):
            c.request('POST','/api/payments/stripe-test/webhook',raw,{'Content-Type':'application/json','Stripe-Signature':f't={stamp},v1={sig}'})
            r=c.getresponse();status=r.status;d=json.loads(r.read());c.close()
        return status,d
    def test_unconfigured_provider_is_not_fake_success(self):
        bid=self.booking()
        with patch.dict(os.environ,{'HS_STRIPE_TEST_SECRET_KEY':''}):
            self.assertEqual(503,self.action(self.learner,bid,'checkout-test')[0])
        with server.connect() as db:self.assertEqual(0,db.execute('SELECT count(*) FROM ledger').fetchone()[0])
    def test_signed_provider_event_reconciles_once_and_rejects_tampering(self):
        bid=self.booking();self.checkout(bid)
        self.assertEqual(409,self.action(self.learner,bid,'pay-test')[0])
        self.assertEqual(400,self.webhook(signature_bad=True)[0]);self.assertEqual(400,self.webhook(changes={'amount_total':1})[0])
        for event in ['evt_http_1','evt_http_1','evt_http_2']:self.assertEqual(200,self.webhook(event)[0])
        with server.connect() as db:
            self.assertEqual(1,db.execute("SELECT count(*) FROM ledger WHERE kind='test_charge'").fetchone()[0]);self.assertEqual(2,db.execute('SELECT count(*) FROM provider_events').fetchone()[0]);self.assertEqual('test_paid',db.execute('SELECT status FROM bookings WHERE id=?',(bid,)).fetchone()[0])
    def test_late_provider_event_is_held_without_reopening_booking(self):
        bid=self.booking();self.checkout(bid);self.clock+=1000
        status,data=self.webhook();self.assertEqual(200,status);self.assertTrue(data['heldForReview'])
        with server.connect() as db:self.assertEqual('expired',db.execute('SELECT status FROM bookings WHERE id=?',(bid,)).fetchone()[0]);self.assertEqual(0,db.execute('SELECT count(*) FROM ledger').fetchone()[0])
    def test_expired_hold_releases_slot_and_does_not_charge(self):
        # Fixture slot begins10m ahead; use later slot to exercise the15m hold itself.
        _,slot=self.teacher.call('/api/availability',{'start':self.clock+5000,'end':self.clock+9000})
        _,b=self.book(slot=slot['slotId']);self.clock+=901
        self.assertEqual(200,self.learner.call('/api/bookings')[0])
        status,new=self.book(client=self.outsider,slot=slot['slotId']);self.assertEqual(200,status,new)
        self.assertEqual(409,self.action(self.learner,b['bookingId'],'pay-test')[0])
    def test_supabase_identity_mapping_ignores_admin_claim_and_email_takeover(self):
        client=fixtures.Client(self.http.server_port)
        verified={'projectRef':'abcdefghijklmnopqrst','subject':'11111111-1111-4111-8111-111111111111','email':'cloud-test@example.test'}
        with patch.object(server.supabase_auth,'verify_user',lambda token:verified):
            status,data=client.call('/api/auth/supabase',{'token':'contract-token','role':'teacher','nickname':'CloudTeacher','adultConsent':True});self.assertEqual(200,status);self.assertEqual('teacher',data['user']['role']);self.assertFalse(data['user']['approved'])
            self.assertEqual(400,client.call('/api/auth/supabase',{'token':'contract-token','role':'admin','nickname':'CloudTeacher','adultConsent':True})[0]);self.assertEqual(403,client.call('/api/admin')[0])
            verified.update(subject='22222222-2222-4222-8222-222222222222',email='learner@example.com')
            self.assertEqual(409,client.call('/api/auth/supabase',{'token':'contract-token','role':'learner','nickname':'MustNotLink','adultConsent':True})[0])
    def test_bad_login_counter_not_reset_by_another_accounts_success(self):
        client=fixtures.Client(self.http.server_port)
        for _ in range(11):self.assertEqual(401,client.call('/api/login',{'email':'learner@example.com','password':'wrongpassword'})[0])
        self.assertEqual(200,client.call('/api/login',{'email':'outsider@example.com','password':'Password12345!'})[0])
        self.assertEqual(401,client.call('/api/login',{'email':'learner@example.com','password':'wrongpassword'})[0]);self.assertEqual(429,client.call('/api/login',{'email':'learner@example.com','password':'wrongpassword'})[0])

if __name__=='__main__':unittest.main()
