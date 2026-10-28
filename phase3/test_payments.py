"""Offline contract fixtures, not evidence that a Stripe account/sandbox was run."""
import copy
import hashlib
import hmac
import json
import unittest
from urllib.parse import parse_qs
import payments

class PaymentContractTests(unittest.TestCase):
    def setUp(self):
        self.booking={'id':'booking_123','price':20000}
        self.secret='whsec_offline_contract_secret_123'
        self.obj={'id':'cs_test_123','object':'checkout.session','livemode':False,'mode':'payment','payment_status':'paid','status':'complete','amount_total':20000,'currency':'krw','client_reference_id':'booking_123','metadata':{'booking_id':'booking_123','hs_mode':'phase3-test-only'},'url':'https://checkout.stripe.com/c/pay/cs_test_123'}
        self.event={'id':'evt_test_123','livemode':False,'type':'checkout.session.completed','data':{'object':self.obj}}
    def signed(self,event=None,timestamp=2000000000):
        raw=json.dumps(event or self.event,separators=(',',':')).encode()
        signature=hmac.new(self.secret.encode(),str(timestamp).encode()+b'.'+raw,hashlib.sha256).hexdigest()
        return raw,f't={timestamp},v1={signature}'
    def checkout(self,transport,**extra):
        return payments.create_checkout(self.booking,success_url='http://127.0.0.1:8765/?payment=return',cancel_url='http://127.0.0.1:8765/?payment=cancel',api_key='sk_test_contract_123456',transport=transport,**extra)
    def test_provider_request_uses_server_amount_and_stable_idempotency(self):
        captured=[]
        def transport(req,timeout):
            captured.append(req)
            self.assertEqual(15,timeout)
            return json.dumps(self.obj).encode()
        for _ in range(2):self.assertEqual('provider-test',self.checkout(transport)['mode'])
        req=captured[0];d=parse_qs(req.data.decode())
        self.assertEqual(payments.ENDPOINT,req.full_url)
        self.assertEqual(['20000'],d['line_items[0][price_data][unit_amount]']) # KRW has no x100 scaling.
        self.assertEqual(['krw'],d['line_items[0][price_data][currency]'])
        self.assertEqual(['booking_123'],d['metadata[booking_id]'])
        self.assertEqual(captured[0].get_header('Idempotency-key'),captured[1].get_header('Idempotency-key'))
        self.assertNotIn('customer_email',d)
    def test_unconfigured_and_live_keys_cannot_make_network_request(self):
        for key in ['', 'sk_live_never_use_this', 'rk_live_never_use_this', 'rk_test_not_supported']:
            with self.subTest(key=key),self.assertRaises(payments.PaymentError):
                payments.create_checkout(self.booking,success_url='https://example.test',cancel_url='https://example.test',api_key=key,transport=lambda *_:self.fail('network must not run'))
    def test_bad_provider_response_and_redirect_are_rejected(self):
        for change in [{'livemode':True},{'amount_total':19999},{'amount_total':20000.0},{'currency':'usd'},{'url':'https://evil.test/c/pay/123'},{'id':'cs_live_123'},{'metadata':[]}]:
            obj=copy.deepcopy(self.obj);obj.update(change)
            with self.subTest(change=change),self.assertRaises(payments.PaymentError):self.checkout(lambda *a,**kw:json.dumps(obj).encode())
    def test_signed_raw_payload_success_and_key_rotation(self):
        raw,signature=self.signed();signature+=',v1='+'0'*64
        verified=payments.verify_event(raw,signature,self.secret,now=2000000000)
        result=payments.validate_checkout_event(verified,self.booking,'cs_test_123')
        self.assertEqual('evt_test_123',result['event_id']);self.assertEqual(20000,result['amount'])
    def test_payload_tampering_expiry_future_and_duplicate_timestamp_denied(self):
        raw,signature=self.signed()
        failures=[(raw+b' ',signature,2000000000),(raw,signature,2000000301),(raw,signature,1999999699),(raw,signature+',t=2000000000',2000000000),(raw,'t=2000000000,v1=bad',2000000000)]
        for payload,sig,now in failures:
            with self.subTest(sig=sig),self.assertRaises(payments.PaymentError):payments.verify_event(payload,sig,self.secret,now=now)
    def test_live_webhook_rejected_even_with_valid_signature(self):
        event=copy.deepcopy(self.event);event['livemode']=True;raw,sig=self.signed(event)
        with self.assertRaises(payments.PaymentError):payments.verify_event(raw,sig,self.secret,now=2000000000)
    def test_success_event_must_match_preexisting_session_booking_currency_amount(self):
        changes=[{'id':'cs_test_other'},{'payment_status':'unpaid'},{'status':'open'},{'amount_total':2000000},{'amount_total':20000.0},{'amount_total':True},{'currency':'usd'},{'client_reference_id':'other'},{'metadata':{'booking_id':'other','hs_mode':'phase3-test-only'}},{'livemode':True}]
        for change in changes:
            event=copy.deepcopy(self.event);event['data']['object'].update(change)
            with self.subTest(change=change),self.assertRaises(payments.PaymentError):payments.validate_checkout_event(event,self.booking,'cs_test_123')
    def test_unsupported_refund_connect_and_malformed_events_never_mark_paid(self):
        for change in [{'type':'charge.refunded'},{'data':[]},{'account':'acct_external'},{'id':None}]:
            event=copy.deepcopy(self.event);event.update(change)
            with self.subTest(change=change),self.assertRaises(payments.PaymentError):payments.validate_checkout_event(event,self.booking,'cs_test_123')
    def test_replay_contract_uses_event_and_session_identifiers(self):
        # Persistence is owned by caller transaction, not an in-memory set in production.
        raw,sig=self.signed();event=payments.verify_event(raw,sig,self.secret,now=2000000000)
        one=payments.validate_checkout_event(event,self.booking,'cs_test_123')
        two=payments.validate_checkout_event(event,self.booking,'cs_test_123')
        self.assertEqual(one,two) # Root must store event_id+session_id UNIQUE and acknowledge retry safely.

if __name__=='__main__':unittest.main()
