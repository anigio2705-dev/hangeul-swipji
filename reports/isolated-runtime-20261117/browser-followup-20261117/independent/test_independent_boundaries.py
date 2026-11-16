"""Independent adversarial HTTP cases; real SQLite, synthetic users/time only."""
import sys,os
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(os.environ.get('HS_REVIEW_SOURCE',str(Path(__file__).resolve().parent.parent/'hangeul-isolated-review-20261117')))/'phase3'))
import test_server as fixture
import server

class IndependentBoundaries(unittest.TestCase):
    setUp=fixture.PlatformTests.setUp
    tearDown=fixture.PlatformTests.tearDown
    register=fixture.PlatformTests.register
    book=fixture.PlatformTests.book
    booking=fixture.PlatformTests.booking
    action=fixture.PlatformTests.action
    finish=fixture.PlatformTests.finish
    def case(self):
        bid=self.booking();self.action(self.learner,bid,'pay-test')
        status,case=self.action(self.learner,bid,'dispute',{'category':'refund','reason':'Independent local refund dispute for boundaries.'})
        self.assertEqual(200,status)
        return bid,case['disputeId']

    def test_other_account_and_admin_cannot_forge_counterpart_statement(self):
        bid,did=self.case();endpoint=f'/api/bookings/{bid}/disputes/{did}/statements'
        for actor in (self.outsider,self.admin):
            status,body=actor.call(endpoint,{'text':'Forged counterpart statement from wrong identity.'});self.assertEqual(403,status,body)
        status,body=self.learner.call(endpoint,{'text':'I pretend to be the counterpart','authorId':self.t['id']})
        self.assertEqual(400,status,body)
        status,body=self.learner.call(endpoint,{'text':'Legitimate reporter statement cannot replace counterpart.'});self.assertEqual(200,status,body)
        status,body=self.admin.call('/api/admin/disputes/'+did,{'decision':'refund','reason':'Independent test review must still require real counterpart.'})
        self.assertEqual(409,status,body)
        with server.connect() as db:
            self.assertEqual(0,db.execute('SELECT count(*) FROM dispute_statements WHERE author_id=?',(self.t['id'],)).fetchone()[0])
            self.assertEqual(0,db.execute('SELECT count(*) FROM local_refund_requests').fetchone()[0])

    def test_same_request_changed_amount_is_rejected_and_ledger_unchanged(self):
        bid,did=self.case();endpoint=f'/api/bookings/{bid}/disputes/{did}/statements'
        self.assertEqual(200,self.teacher.call(endpoint,{'text':'Independent counterpart evidence for refund.'})[0])
        with server.connect() as db:original=db.execute("SELECT id,amount FROM ledger WHERE booking_id=? AND kind='test_charge'",(bid,)).fetchone()
        refund='/api/admin/disputes/'+did
        body={'decision':'refund','reason':'Independent explicitly allocated virtual refund.','requestId':'independent-refund-1','amount':10000,'allocations':{str(original['id']):10000}}
        status,result=self.admin.call(refund,body);self.assertEqual(200,status,result)
        with server.connect() as db:before=[tuple(r) for r in db.execute('SELECT * FROM ledger ORDER BY id')]
        changed=dict(body,amount=10001,allocations={str(original['id']):10001})
        status,result=self.admin.call(refund,changed);self.assertEqual(409,status,result)
        with server.connect() as db:self.assertEqual(before,[tuple(r) for r in db.execute('SELECT * FROM ledger ORDER BY id')])

    def test_placement_and_profile_are_owned_by_authenticated_user(self):
        self.assertEqual(200,self.learner.call('/api/learning/placement',{'groups':[3,2,1,0],'userId':self.o['id']})[0])
        self.assertIsNotNone(self.learner.call('/api/learning')[1]['placement'])
        self.assertIsNone(self.outsider.call('/api/learning')[1]['placement'])
        before=self.outsider.call('/api/me')[1]['user']
        status,result=self.learner.call('/api/profile',{'nickname':'Independent saved learner','id':self.o['id']},'PUT')
        self.assertEqual(200,status,result)
        self.assertEqual(before,self.outsider.call('/api/me')[1]['user'])
        self.assertEqual('Independent saved learner',self.learner.call('/api/me')[1]['user']['nickname'])

    def test_revoked_session_does_not_return_after_server_recreation(self):
        import threading
        cookie=self.learner.cookie;self.assertEqual(200,self.learner.call('/api/logout',{})[0])
        self.http.shutdown();self.http.server_close();self.thread.join()
        self.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);self.http.failures={}
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.learner.port=self.http.server_port;self.learner.cookie=cookie
        status,result=self.learner.call('/api/me');self.assertEqual(401,status,result)

if __name__=='__main__':unittest.main(verbosity=2)
