"""Independent second-pass adversarial regressions using disposable local fixtures."""
import unittest
import test_server as fixtures
import server

class RoundTwoTests(unittest.TestCase):
    setUp = fixtures.PlatformTests.setUp
    tearDown = fixtures.PlatformTests.tearDown
    register = fixtures.PlatformTests.register
    book = fixtures.PlatformTests.book
    booking = fixtures.PlatformTests.booking
    action = fixtures.PlatformTests.action

    def test_nonoverlapping_attendance_cannot_complete_a_conversation(self):
        bid=self.booking()
        self.assertEqual(200,self.action(self.learner,bid,'pay-test')[0])
        self.clock+=600
        self.assertEqual(200,self.action(self.teacher,bid,'join')[0])
        for _ in range(30):
            self.clock+=60
            self.assertEqual(200,self.action(self.teacher,bid,'attendance')[0])
        self.action(self.teacher,bid,'complete')
        # Teacher stops before learner first enters: each accumulates 30m, shared time is 0.
        self.assertEqual(200,self.action(self.learner,bid,'join')[0])
        for _ in range(30):
            self.clock+=60
            self.assertEqual(200,self.action(self.learner,bid,'attendance')[0])
        self.assertEqual(200,self.admin.call('/api/admin/evidence',{'bookingId':bid,'reason':'Independent test manual evidence must not override zero shared attendance'})[0])
        status,_=self.action(self.learner,bid,'complete')
        self.assertEqual(409,status)
        with server.connect() as db:
            self.assertNotEqual('completed',db.execute('SELECT status FROM bookings WHERE id=?',(bid,)).fetchone()[0])
        self.assertEqual(409,self.admin.call('/api/admin/settle',{'bookingId':bid})[0])

    def test_past_unpaid_booking_cannot_record_new_charge(self):
        bid=self.booking()
        self.clock+=5000
        status,_=self.action(self.learner,bid,'pay-test')
        self.assertIn(status,(409,410))
        with server.connect() as db:
            self.assertEqual(0,db.execute("SELECT count(*) FROM ledger WHERE booking_id=? AND kind='test_charge'",(bid,)).fetchone()[0])

    def test_initial_booking_referrer_cannot_change_on_later_booking(self):
        first,ref1=self.register('learner','referrer-first')
        second,ref2=self.register('learner','referrer-second')
        status,booked=self.book(referral=ref1['referral_code']);self.assertEqual(200,status)
        self.assertEqual(200,self.action(self.learner,booked['bookingId'],'cancel')[0])
        status,_=self.book(referral=ref2['referral_code'])
        self.assertIn(status,(400,409))
        with server.connect() as db:
            distinct=db.execute('SELECT count(distinct referrer_id) FROM bookings WHERE learner_id=?',(self.l['id'],)).fetchone()[0]
            self.assertEqual(1,distinct)

if __name__=='__main__':unittest.main()
