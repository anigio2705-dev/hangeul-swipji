"""Local HTTP/SQLite review: current workflow, never external accounts or money."""
import unittest
import test_server as fixture
import server

class CurrentWorkflowReview(unittest.TestCase):
    setUp=fixture.PlatformTests.setUp
    tearDown=fixture.PlatformTests.tearDown
    register=fixture.PlatformTests.register
    book=fixture.PlatformTests.book
    booking=fixture.PlatformTests.booking
    action=fixture.PlatformTests.action
    finish=fixture.PlatformTests.finish

    def statement(self,bid,did):
        status,body=self.teacher.call(f'/api/bookings/{bid}/disputes/{did}/statements',{'text':'Counterpart statement for isolated regression review.'})
        self.assertEqual(200,status,body)

    def test_full_refund_requires_counterpart_then_zeroes_teacher_and_replays_once(self):
        bid=self.booking();self.finish(bid)
        self.assertEqual(200,self.admin.call('/api/admin/settle',{'bookingId':bid})[0])
        self.assertEqual(16000,self.teacher.call('/api/earnings')[1]['teacherAccrued'])
        _,case=self.action(self.learner,bid,'dispute',{'category':'refund','reason':'Isolated current refund workflow evidence.'})
        endpoint='/api/admin/disputes/'+case['disputeId'];body={'decision':'refund','reason':'Isolated administrator evidence after counterpart review.'}
        self.assertEqual(409,self.admin.call(endpoint,body)[0])
        self.statement(bid,case['disputeId'])
        status,result=self.admin.call(endpoint,body);self.assertEqual(200,status,result)
        self.assertFalse(result['realRefund'])
        self.assertEqual(0,self.teacher.call('/api/earnings')[1]['teacherAccrued'])
        with server.connect() as db:before=db.execute('SELECT count(*) FROM ledger').fetchone()[0]
        status,replayed=self.admin.call(endpoint,body);self.assertEqual(200,status,replayed);self.assertTrue(replayed['duplicate'])
        with server.connect() as db:self.assertEqual(before,db.execute('SELECT count(*) FROM ledger').fetchone()[0])

    def test_reschedule_requires_statement_and_both_actual_consents(self):
        bid=self.booking();self.action(self.learner,bid,'pay-test')
        _,replacement=self.teacher.call('/api/availability',{'start':self.clock+5000,'end':self.clock+8600})
        _,case=self.action(self.learner,bid,'dispute',{'category':'connection','reason':'Isolated mutually agreed reschedule evidence.'})
        endpoint='/api/admin/disputes/'+case['disputeId'];body={'decision':'reschedule','slotId':replacement['slotId'],'reason':'Isolated administrator verifies both participant consents.'}
        self.assertEqual(409,self.admin.call(endpoint,body)[0]);self.statement(bid,case['disputeId'])
        self.assertEqual(400,self.admin.call(endpoint,body)[0])
        self.assertEqual(200,self.action(self.learner,bid,'reschedule-consent',{'slotId':replacement['slotId']})[0])
        self.assertEqual(400,self.admin.call(endpoint,body)[0])
        self.assertEqual(200,self.action(self.teacher,bid,'reschedule-consent',{'slotId':replacement['slotId']})[0])
        status,result=self.admin.call(endpoint,body);self.assertEqual(200,status,result)
        with server.connect() as db:self.assertEqual(replacement['slotId'],db.execute('SELECT slot_id FROM bookings WHERE id=?',(bid,)).fetchone()[0])

    def test_saved_profile_and_bookings_survive_http_server_recreation(self):
        import threading
        bid=self.booking()
        status,result=self.learner.call('/api/profile',{'nickname':'Saved test learner'},'PUT');self.assertEqual(200,status,result)
        self.http.shutdown();self.http.server_close();self.thread.join()
        self.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);self.http.failures={}
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.learner.port=self.http.server_port;self.outsider.port=self.http.server_port
        status,me=self.learner.call('/api/me');self.assertEqual(200,status,me);self.assertEqual('Saved test learner',me['user']['nickname'])
        status,saved=self.learner.call('/api/bookings');self.assertEqual(200,status,saved);self.assertIn(bid,[x['id'] for x in saved['bookings']])
        self.assertEqual([],self.outsider.call('/api/bookings')[1]['bookings'])

if __name__=='__main__':unittest.main(verbosity=2)
