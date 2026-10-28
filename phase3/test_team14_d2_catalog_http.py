"""D2 actual HTTP -> Team13 verified completion -> 75/25 catalog ledger, refund and replay."""
import unittest
import server
from team14_persistent import SimError
from team14_initial_products import (TEST_CATALOG,bind_server_booking_product,
                                     expected_split)
from team14_instant_verified_bridge import settle_verified_instant_event
from team14_refund_workflow import request_refund,decide_refund,apply_approved_refund
from test_team14_instant_http_settlement import InstantSettlementJourney as Journey

class D2CatalogHttpTests(unittest.TestCase):
    setUp=Journey.setUp
    tearDown=Journey.tearDown
    request=Journey.request
    def account(self,email,role='learner',approved=False,referral_code=None):
        cookie,uid=Journey.account(self,email,role,approved,referral_code)
        # Existing Team13 creates instant bookings from users.price.
        # Simulate the 11/13 product selection BEFORE a match, never mutate
        # the booking or completion event after it was generated.
        if role=='partner':
            with server.connect() as db:
                db.execute('UPDATE users SET price=? WHERE id=?',
                           (TEST_CATALOG['partner_25'][1],uid))
        return cookie,uid

    call=Journey.call
    journey=Journey.journey
    prepare_settlement=Journey.prepare_settlement
    dispose_settlement=Journey.dispose_settlement

    def test_http_verified_completion_75_25_refund_replay_restart(self):
        self.prepare_settlement()
        try:
            learner,_,_,booking,event,price=self.journey()
            self.assertEqual(price,TEST_CATALOG['partner_25'][1],
                             '13/14 contract conflict: partner default price is not 10000')
            with server.connect() as db:
                # Team13 now creates this snapshot atomically with booking.
                # Verify the actual server record instead of inserting a fixture.
                snapshot=db.execute(
                    'SELECT product_code,duration_minutes,price_krw,currency '
                    'FROM booking_product_snapshots WHERE booking_id=?',
                    (booking,)).fetchone()
                self.assertIsNotNone(snapshot, 'Team13 did not persist the booking product')
                self.assertEqual(tuple(snapshot),('partner_25',25,10000,'KRW'))
                p=bind_server_booking_product(db,self.store,'d2month',booking,
                                              'partner_25',300)
                self.assertFalse(p['payment_executed'])
                self.assertEqual(p['test_price_krw'],10000)
                first=settle_verified_instant_event(db,self.store,self.referrals,event)
                self.assertEqual(first,settle_verified_instant_event(db,self.store,self.referrals,event))
                total=self.store.totals('d2month')
                self.assertEqual((total['teacher'],total['referral'],total['platform']),
                                 (7500,300,2200))
                self.assertFalse(first['payment_executed'])
                request_refund(db,self.store,booking,'d2-refund',learner,4000)
                decide_refund(self.store,'d2-refund','approved','test_reviewer')
                applied=apply_approved_refund(db,self.store,'d2-refund')
                self.assertEqual(applied,apply_approved_refund(db,self.store,'d2-refund'))
                after=self.store.totals('d2month')
                self.assertEqual((after['teacher'],after['referral'],after['platform']),
                                 (4500,180,1320))
                self.assertEqual(after['refunded'],4000)
            self.store.close();self.referrals.close()
            from team14_persistent import MonthlyStore
            from team14_referral_store import ReferralStore
            self.store=MonthlyStore(self.sp)
            self.referrals=ReferralStore(self.rp)
            with server.connect() as db:
                self.assertEqual(first,settle_verified_instant_event(db,self.store,self.referrals,event))
                self.assertEqual(applied,apply_approved_refund(db,self.store,'d2-refund'))
            self.assertEqual(after,self.store.totals('d2month'))
        finally:
            self.dispose_settlement()

    def test_catalog_price_and_role_mismatch_rejected(self):
        self.prepare_settlement()
        try:
            _,_,_,booking,event,price=self.journey()
            with server.connect() as db:
                # No trusted Team13 snapshot => both catalog binding paths fail closed.
                with self.assertRaises(SimError):
                    bind_server_booking_product(db,self.store,'wrongprice',booking,'trial_15')
                with self.assertRaises(SimError):
                    bind_server_booking_product(db,self.store,'wrongrole',booking,'professional_25')
                self.assertEqual(0,self.store.db.execute('SELECT COUNT(*) FROM months').fetchone()[0])
        finally:
            self.dispose_settlement()

if __name__=='__main__':
    unittest.main(verbosity=2)
